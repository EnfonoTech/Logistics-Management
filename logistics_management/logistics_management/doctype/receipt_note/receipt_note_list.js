// Copyright (c) 2026, siva and contributors
// For license information, please see license.txt

// Movement: pick any set of submitted, move-flagged receipts and consolidate them into
// ONE job. There is deliberately no same-customer gate here -- a console job holding
// many customers is the requirement. The old button hid itself unless every selected
// row shared a consignee, which was the exact opposite.

frappe.listview_settings["Receipt Note"] = {
    add_fields: ["consignee", "warehouse_unit", "disposition", "job_status", "total_cbm", "wms_status"],

    get_indicator(doc) {
        const colours = {
            "In Warehouse": "blue",
            "In Movement": "orange",
            "Arrived at Destination": "purple",
            Delivered: "green",
        };
        if (doc.docstatus === 1 && doc.wms_status) {
            return [__(doc.wms_status), colours[doc.wms_status] || "gray", `wms_status,=,${doc.wms_status}`];
        }
    },

    onload(listview) {
        listview.page.add_inner_button(__("Create Movement Job"), () => {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("Select the Receipt Notes to move."));
                return;
            }
            open_movement_dialog(listview, selected);
        });
    },
};

function open_movement_dialog(listview, selected) {
    const blocked = selected.filter(
        (d) =>
            d.docstatus !== 1 ||
            d.job_status === "Created" ||
            (d.disposition && d.disposition !== "Move to Other Warehouse")
    );
    if (blocked.length) {
        frappe.msgprint({
            title: __("Some receipts cannot be moved"),
            indicator: "red",
            message:
                __("These are either not submitted, already on a job, or marked for storage:") +
                "<br>" +
                blocked.map((d) => frappe.utils.escape_html(d.name)).join("<br>"),
        });
        return;
    }

    const origins = Array.from(new Set(selected.map((d) => d.warehouse_unit).filter(Boolean)));
    if (origins.length !== 1) {
        frappe.msgprint({
            title: __("One origin per console"),
            indicator: "red",
            message: __("The selected receipts span {0} warehouses. A console ships from one.", [
                origins.length,
            ]),
        });
        return;
    }

    const origin = origins[0];
    const customers = Array.from(new Set(selected.map((d) => d.consignee).filter(Boolean)));
    const total_cbm = selected.reduce((sum, d) => sum + flt(d.total_cbm), 0);

    frappe.call({
        method: "logistics_management.wms.consolidation.get_movement_defaults",
        args: { warehouse_unit: origin },
        callback: (r) => {
            const defaults = r.message || {};
            const dialog = new frappe.ui.Dialog({
                title: __("Create Movement Job"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `<div class="text-muted small">${__(
                            "{0} waybills for {1} customer(s), {2} CBM, leaving {3}.",
                            [
                                selected.length,
                                customers.length,
                                format_number(total_cbm, null, 2),
                                frappe.utils.escape_html(origin),
                            ]
                        )}</div>`,
                    },
                    {
                        fieldname: "destination_warehouse",
                        fieldtype: "Link",
                        options: "Warehouse Unit",
                        label: __("Destination Warehouse"),
                        reqd: 1,
                        get_query: () => ({ filters: { name: ["!=", origin] } }),
                    },
                    {
                        fieldname: "mode_of_transport",
                        fieldtype: "Select",
                        options: "AIR\nSEA\nLAND",
                        label: __("Mode of Transport"),
                        reqd: 1,
                        default: defaults.mode_of_transport || "LAND",
                    },
                    {
                        fieldname: "movement_date",
                        fieldtype: "Date",
                        label: __("Date of Movement"),
                        reqd: 1,
                        default: defaults.movement_date || frappe.datetime.get_today(),
                    },
                    {
                        fieldname: "shipment_mode",
                        fieldtype: "Select",
                        options: "IMPORT\nEXPORT\nRE-EXPORT\nLOCAL",
                        label: __("Shipment Mode"),
                        default: "IMPORT",
                    },
                ],
                primary_action_label: __("Create Job"),
                primary_action(values) {
                    dialog.hide();
                    frappe.call({
                        method: "logistics_management.wms.consolidation.create_console_job_from_receipts",
                        args: Object.assign({ receipt_notes: selected.map((d) => d.name) }, values),
                        freeze: true,
                        freeze_message: __("Consolidating waybills into one job..."),
                        callback: (res) => {
                            if (res.exc) return;
                            frappe.show_alert(
                                {
                                    message: __("Job {0} created with {1} waybills", [
                                        res.message.job,
                                        res.message.waybill_consoles.length,
                                    ]),
                                    indicator: "green",
                                },
                                7
                            );
                            frappe.set_route("Form", "Job Details", res.message.job);
                        },
                    });
                },
            });
            dialog.show();
        },
    });
}
