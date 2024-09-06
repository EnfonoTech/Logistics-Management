frappe.ui.form.on("Job Details", {
    refresh: function(frm) {
        add_custom_buttons(frm);
        frm.events.set_dashboard_indicators(frm);
    },

    set_dashboard_indicators: function(frm) {
        // Use the company field from Job Details to trigger company-specific logic
        if (frm.doc.company) {
            handle_company_specific_logic(frm);
        }
    }
});

function handle_company_specific_logic(frm) {
    var company = frm.doc.company;

    // Define company-specific behavior for the two companies
    var companyLogic = {
        'HARBOUR SHIPPING AND MARINE SERVICES': function() {
            process_company_data(frm, false);  // Logic for this company
        },
        'HARBOUR SHIPPING AND MARINE SERVICES WLL-NVOCC DIVISION': function() {
            process_company_data(frm, true);  // Logic for the NVOCC Division
        },
        'DEFAULT': function() {
            process_company_data(frm, false);  // Default logic for other companies
        }
    };

    // Execute logic for the selected company or default if no match
    if (companyLogic[company]) {
        companyLogic[company]();
    } else {
        companyLogic['DEFAULT']();
    }
}

function process_company_data(frm, isNVOCCDivision) {
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

function add_custom_buttons(frm) {
    frm.add_custom_button(__('Job Ledger'), function() {
        frappe.set_route('query-report', 'Job Details Metric', {
            job_details: frm.doc.name
        });
    }, __('View'));
}
