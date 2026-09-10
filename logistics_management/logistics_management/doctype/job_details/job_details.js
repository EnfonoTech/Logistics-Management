frappe.ui.form.on("Job Details", {
    refresh: function(frm) {
        add_custom_buttons(frm);
        frm.events.set_dashboard_indicators(frm);
    },

    set_dashboard_indicators: function(frm) {
        function process_invoices(invoices, includeOutstanding = false) {
            var totals = { grandTotal: 0, outstandingTotal: 0 };
            if (invoices && invoices.length > 0) {
                invoices.forEach(function(invoice) {
                    totals.grandTotal += invoice.base_grand_total;
                    if (includeOutstanding) {
                        totals.outstandingTotal += invoice.outstanding_amount;
                    }
                });
            }
            return totals;
        }

        function process_journal_entries(entries) {
            var totalDebit = 0;
            if (entries && entries.length > 0) {
                entries.forEach(function(entry) {
                    totalDebit += entry.total_debit;
                });
            }
            return totalDebit;
        }

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Sales Invoice',
                filters: {
                    custom_job_number: frm.doc.name,
                    docstatus: 1
                },
                fields: ['base_grand_total', 'outstanding_amount']
            },
            callback: function(response) {
                var salesInvoiceTotals = process_invoices(response.message, true);

                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Purchase Invoice',
                        filters: {
                            custom_job_number: frm.doc.name,
                            docstatus: 1
                        },
                        fields: ['base_grand_total', 'outstanding_amount']
                    },
                    callback: function(response) {
                        var purchaseInvoiceTotals = process_invoices(response.message, true);

                        frappe.call({
                            method: 'frappe.client.get_list',
                            args: {
                                doctype: 'Journal Entry',
                                filters: {
                                    custom_job_number: frm.doc.name,
                                    docstatus: 1
                                },
                                fields: ['total_debit']
                            },
                            callback: function(response) {
                                var journalEntryTotalDebit = process_journal_entries(response.message);

                                var totalExpenses = purchaseInvoiceTotals.grandTotal + journalEntryTotalDebit;
                                var profitAndLoss = salesInvoiceTotals.grandTotal - totalExpenses;

                                frm.dashboard.add_indicator(
                                    __('Total Sales Invoice: {0}', [format_currency(salesInvoiceTotals.grandTotal, frm.doc.currency)]), 
                                    'blue'
                                );
                                frm.dashboard.add_indicator(
                                    __('Total Purchase Invoice: {0}', [format_currency(purchaseInvoiceTotals.grandTotal, frm.doc.currency)]), 
                                    'orange'
                                );
                                frm.dashboard.add_indicator(
                                    __('Total Journal Entries: {0}', [format_currency(journalEntryTotalDebit, frm.doc.currency)]), 
                                    'purple'
                                );
                                frm.dashboard.add_indicator(
                                    __('P&L: {0}', [format_currency(profitAndLoss, frm.doc.currency)]), 
                                    profitAndLoss >= 0 ? 'green' : 'red'
                                );
                            }
                        });
                    }
                });
            }
        });
    }
});

function add_custom_buttons(frm) {
    frm.add_custom_button(__('Job Ledger'), function() {
        frappe.set_route('query-report', 'Job Details Metric', {
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
    const group = __("Warehouse");

    if (!frm.doc.wms_arrival_confirmed) {
        frm.add_custom_button(__("Confirm Arrival"), () => confirm_arrival(frm), group);
    } else {
        frm.add_custom_button(__("Deliver Waybill"), () => deliver_waybill(frm), group);
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
