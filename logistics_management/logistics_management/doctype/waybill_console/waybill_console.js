// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

frappe.ui.form.on("Waybill Console", {
    refresh: function(frm) {
        // add_custom_buttons(frm);
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

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Sales Invoice',
                filters: {
                    custom_waybill_console: frm.doc.name,
                    docstatus: 1
                },
                fields: ['base_grand_total', 'outstanding_amount']
            },
            callback: function(response) {
                var salesInvoiceTotals = process_invoices(response.message, true);

                frm.dashboard.add_indicator(
                    __('Total Sales Invoice: {0}', [format_currency(salesInvoiceTotals.grandTotal, frm.doc.currency)]), 
                    'blue'
                );
            }
        });
    }
});
