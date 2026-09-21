// ─────────────────────────────────────────────────────────────────────────────────
// Job Summary.
//
// The money on a job is the first thing an operator wants off this screen. It used to
// arrive as four indicator pills, computed by three frappe.client.get_list calls nested
// in each other's callbacks -- three sequential round trips before anything appeared.
// One read-only endpoint now returns all of it, and it is drawn as cards.
// ─────────────────────────────────────────────────────────────────────────────────

const JOB_STATUS_COLOURS = {
    "Pending": "orange",
    "In Progress": "blue",
    "Completed": "green",
    "On Hold": "yellow",
    "Cancelled": "red",
};

const CARD_INK = {
    revenue: "#1C4AA0",
    cost: "#55616f",
    good: "#2e9e5b",
    warn: "#a36a00",
    bad: "#b3261e",
};

frappe.ui.form.on("Job Details", {
    refresh: function (frm) {
        add_custom_buttons(frm);
        set_status_indicator(frm);
        show_job_summary(frm);
    },
});

function set_status_indicator(frm) {
    // Which of the five states a job is in, on the title, instead of scrolled to
    // somewhere past field 84.
    if (frm.is_new() || !frm.doc.job_status) return;
    frm.page.set_indicator(
        __(frm.doc.job_status),
        JOB_STATUS_COLOURS[frm.doc.job_status] || "gray"
    );
}

function show_job_summary(frm) {
    if (frm.is_new()) return;

    frappe.call({
        method:
            "logistics_management.logistics_management.doctype.job_details.job_details.get_job_financials",
        args: { job: frm.doc.name },
        callback: (r) => {
            const d = r.message;
            if (!d) return;
            // A job that has never been invoiced or costed has nothing to summarise, and
            // six cards of zero are worse than no cards.
            if (!d.revenue && !d.cost) return;

            render_summary_cards(frm, d);
        },
    });
}

function render_summary_cards(frm, d) {
    const cur = d.currency;
    const margin_ink =
        d.margin === null ? CARD_INK.cost
            : d.margin < 0 ? CARD_INK.bad
            : d.margin < 10 ? CARD_INK.warn
            : CARD_INK.good;

    const tiles = [
        { label: __("Revenue"), value: format_currency(d.revenue, cur), ink: CARD_INK.revenue },
        { label: __("Cost"), value: format_currency(d.cost, cur), ink: CARD_INK.cost },
        { label: __("Gross Profit"), value: format_currency(d.profit, cur), ink: margin_ink },
        {
            label: __("Margin"),
            // Null margin means no revenue yet. That is not a margin of zero.
            value: d.margin === null ? "—" : `${format_number(d.margin, null, 1)}%`,
            ink: margin_ink,
        },
        { label: __("Received"), value: format_currency(d.received, cur), ink: CARD_INK.good },
        {
            label: __("Outstanding"),
            value: format_currency(d.outstanding, cur),
            ink: d.outstanding > 0 ? CARD_INK.warn : CARD_INK.cost,
        },
    ];

    const html = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;padding:4px 0 10px;">
            ${tiles
                .map(
                    (t) => `
                <div style="border:1px solid var(--border-color);border-radius:8px;padding:10px 12px;background:var(--card-bg);">
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--text-muted);">${t.label}</div>
                    <div style="font-size:17px;font-weight:600;color:${t.ink};margin-top:2px;white-space:nowrap;">${t.value}</div>
                </div>`
                )
                .join("")}
        </div>`;

    frm.dashboard.add_section(html, __("Job Summary"));

    if (d.outstanding > 0) {
        frm.dashboard.add_indicator(
            __("{0} still outstanding", [format_currency(d.outstanding, cur)]),
            "orange"
        );
    }
    // The split behind Cost, kept because the old pills showed it and the two numbers
    // are booked in different places.
    if (d.journal_entries) {
        frm.dashboard.add_indicator(
            __("Purchase {0} · Journal {1}", [
                format_currency(d.purchase_invoices, cur),
                format_currency(d.journal_entries, cur),
            ]),
            "gray"
        );
    }
}

function add_custom_buttons(frm) {
    // 🔴 This routed to 'Job Details Metric', one of the eleven duplicate reports pruned
    // on 2026-09-12, so View > Job Ledger has opened an empty query-report page on every
    // job since. Nothing referenced the name in the DB -- no workspace link, no shortcut,
    // no Client Script -- so the reference scan that cleared the prune never saw it: it
    // was hardcoded in this file. 'Job Details Report' is the survivor and takes the same
    // job_details filter.
    frm.add_custom_button(__('Job Ledger'), function() {
        frappe.set_route('query-report', 'Job Details Report', {
            job_details: frm.doc.name
        });
    }, __('View'));

    // frm.add_custom_button(__('Generate Project'), function() {
    //     frappe.call({
    //         method: 'logistics_management.logistics_management.doctype.job_details.job_details.generate_project',
    //         args: {
    //             docname: frm.doc.name
    //         },
    //         callback: function(response) {
    //             if (response.message) {
    //                 frm.reload_doc();
    //                 // frappe.msgprint('Waybill generated successfully.');
    //             }
    //         }
    //     });
    // });
}

// ─────────────────────────────────────────────────────────────────────────────────
// Warehouse movement: arrival at the destination, then delivery per waybill.
// Registered as a second form.on block so the existing buttons above are untouched.
// Frappe merges handlers for the same doctype.
// ─────────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on("Job Details", {
    refresh: function (frm) {
        if (frm.is_new() || frm.doc.job_type !== "CONSOLE") return;
        add_wms_buttons(frm);
        set_wms_headline(frm);
    },
});

function add_wms_buttons(frm) {
    // Top-level buttons, deliberately NOT grouped under a "Warehouse" dropdown.
    //
    // 🔴 A grouped custom button on this form is created but never rendered. Probed live:
    // frm.custom_buttons held both "Confirm Arrival" and the app's own "Job Ledger" while
    // document.querySelectorAll(".custom-btn-group") returned [] and neither label
    // appeared anywhere in document.body.innerText — with zero console errors. So the
    // group's element ends up detached and add_custom_button's "already exists" path just
    // un-hides that orphan. Cost three beats across four capture dry runs.
    //
    // Two actions do not need a dropdown anyway: one click instead of two.
    if (!frm.doc.wms_arrival_confirmed) {
        frm.add_custom_button(__("Confirm Arrival"), () => confirm_arrival(frm));
    } else {
        frm.add_custom_button(__("Deliver Waybill"), () => deliver_waybill(frm));
    }
}

function set_wms_headline(frm) {
    if (frm.doc.wms_arrival_confirmed) {
        frm.dashboard.set_headline(
            __("Arrived at {0} on {1}. Deliver each waybill to its customer.", [
                frm.doc.wms_destination_warehouse || "—",
                frappe.datetime.str_to_user(frm.doc.wms_arrival_date),
            ]),
            "green"
        );
    } else if (frm.doc.wms_origin_warehouse) {
        frm.dashboard.set_headline(
            __("In transit from {0} to {1}. Confirm arrival when the container is received.", [
                frm.doc.wms_origin_warehouse,
                frm.doc.wms_destination_warehouse || __("(destination not set)"),
            ]),
            "orange"
        );
    }
}

function confirm_arrival(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Confirm Arrival"),
        fields: [
            {
                fieldtype: "HTML",
                options: `<div class="text-muted small">${__(
                    "This takes space in the destination warehouse and unlocks delivery. It can only be done once."
                )}</div>`,
            },
            {
                fieldname: "destination_warehouse",
                fieldtype: "Link",
                options: "Warehouse Unit",
                label: __("Destination Warehouse"),
                reqd: 1,
                default: frm.doc.wms_destination_warehouse,
            },
            {
                fieldname: "arrival_date",
                fieldtype: "Date",
                label: __("Arrival Date"),
                reqd: 1,
                default: frappe.datetime.get_today(),
            },
            {
                fieldname: "received_by",
                fieldtype: "Data",
                label: __("Received By"),
            },
        ],
        primary_action_label: __("Confirm Arrival"),
        primary_action(values) {
            dialog.hide();
            frappe.call({
                method: "logistics_management.wms.movement.confirm_arrival",
                args: Object.assign({ job: frm.doc.name }, values),
                freeze: true,
                callback: (r) => {
                    if (r.exc) return;
                    frappe.show_alert(
                        {
                            message: __("{0} CBM received at {1} across {2} waybills", [
                                format_number(r.message.cbm, null, 2),
                                r.message.destination,
                                r.message.receipts,
                            ]),
                            indicator: "green",
                        },
                        7
                    );
                    frm.reload_doc();
                },
            });
        },
    });
    dialog.show();
}

function deliver_waybill(frm) {
    frappe.call({
        method: "logistics_management.wms.movement.get_deliverable_waybills",
        args: { job: frm.doc.name },
        callback: (r) => {
            const waybills = r.message || [];
            if (!waybills.length) {
                frappe.msgprint({
                    title: __("Nothing left to deliver"),
                    indicator: "blue",
                    message: __("Every waybill on this job has been delivered."),
                });
                return;
            }

            const dialog = new frappe.ui.Dialog({
                title: __("Deliver Waybill"),
                fields: [
                    {
                        fieldname: "waybill_console",
                        fieldtype: "Select",
                        label: __("Waybill"),
                        reqd: 1,
                        options: waybills.map((w) => ({
                            value: w.name,
                            label: `${w.waybill_no} — ${w.customer} (${w.volume || 0} CBM)`,
                        })),
                    },
                    {
                        fieldname: "delivery_mode",
                        fieldtype: "Select",
                        label: __("Delivery Mode"),
                        options: "Delivery\nCollection",
                        default: "Delivery",
                        reqd: 1,
                    },
                    {
                        fieldname: "delivery_date",
                        fieldtype: "Date",
                        label: __("Date of Delivery"),
                        default: frappe.datetime.get_today(),
                        reqd: 1,
                    },
                    {
                        fieldname: "collected_by",
                        fieldtype: "Data",
                        label: __("Collected By"),
                    },
                    {
                        fieldtype: "Section Break",
                        label: __("Driver and Vehicle"),
                    },
                    {
                        fieldname: "driver",
                        fieldtype: "Link",
                        options: "Driver",
                        label: __("Driver"),
                        get_query: () => ({ filters: { status: "Active" } }),
                        onchange() {
                            const driver = dialog.get_value("driver");
                            if (!driver) {
                                dialog.set_df_property("driver_info", "options", "");
                                return;
                            }
                            frappe.call({
                                method: "logistics_management.wms.movement.get_driver_details",
                                args: { driver },
                                callback: (dr) => {
                                    const d = dr.message;
                                    if (!d) return;
                                    // Only fill an empty vehicle -- never overwrite a truck
                                    // the user has already chosen for this run.
                                    if (d.vehicle && !dialog.get_value("vehicle")) {
                                        dialog.set_value("vehicle", d.vehicle);
                                    }
                                    const bits = [];
                                    if (d.cell_number) bits.push(frappe.utils.escape_html(d.cell_number));
                                    if (d.license_number)
                                        bits.push(
                                            __("Licence {0}", [frappe.utils.escape_html(d.license_number)])
                                        );
                                    if (d.licence_expired)
                                        bits.push(
                                            `<span class="text-danger">${__("Licence expired")}</span>`
                                        );
                                    dialog.set_df_property(
                                        "driver_info",
                                        "options",
                                        bits.length
                                            ? `<div class="text-muted small">${bits.join(" &middot; ")}</div>`
                                            : ""
                                    );
                                },
                            });
                        },
                    },
                    {
                        fieldname: "driver_info",
                        fieldtype: "HTML",
                    },
                    {
                        fieldname: "column_break_driver",
                        fieldtype: "Column Break",
                    },
                    {
                        fieldname: "vehicle",
                        fieldtype: "Link",
                        options: "Vehicle",
                        label: __("Vehicle"),
                        description: __("Printed on the POD as the assigned vehicle number."),
                    },
                    {
                        fieldtype: "Section Break",
                    },
                    {
                        fieldname: "create_pod",
                        fieldtype: "Check",
                        label: __("Create POD"),
                        default: 1,
                        description: __(
                            "Creates the POD to print, get signed, and upload the scan back onto."
                        ),
                    },
                ],
                primary_action_label: __("Record Delivery"),
                primary_action(values) {
                    dialog.hide();
                    frappe.call({
                        method: "logistics_management.wms.movement.record_delivery",
                        args: values,
                        freeze: true,
                        callback: (res) => {
                            if (res.exc) return;
                            if (res.message.pod) {
                                frappe.set_route("Form", "POD", res.message.pod);
                            } else {
                                frm.reload_doc();
                            }
                        },
                    });
                },
            });
            dialog.show();
        },
    });
}
