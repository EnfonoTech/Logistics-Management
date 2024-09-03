// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

frappe.query_reports["Salesperson Accounts Receivable"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0 // Not required field, it's optional
        }
    ],
    "onload": function(report) {
        // Optional: Custom logic on report load
    },
    "get_data": function() {
        const from_date = frappe.query_report.get_filter_value('from_date');
        const to_date = frappe.query_report.get_filter_value('to_date');
        const customer = frappe.query_report.get_filter_value('customer');

        return new Promise(function(resolve, reject) {
            // Prepare filters for the API call
            const filters = [
                ["posting_date", ">=", from_date],
                ["posting_date", "<=", to_date]
            ];

            if (customer) {
                filters.push(["customer", "=", customer]);
            }

            // Call the ERPNext REST API to get the Accounts Receivable data
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Sales Invoice",
                    fields: ["customer", "base_grand_total", "total_advance", "outstanding_amount"],
                    filters: filters
                },
                callback: function(response) {
                    if (response.message) {
                        // Aggregate data by customer
                        const aggregated_data = response.message.reduce((acc, curr) => {
                            const customer = curr.customer;
                            if (!acc[customer]) {
                                acc[customer] = {
                                    invoiced_amount: 0,
                                    paid_amount: 0,
                                    outstanding_amount: 0
                                };
                            }
                            acc[customer].invoiced_amount += curr.base_grand_total;
                            acc[customer].paid_amount += curr.total_advance;
                            acc[customer].outstanding_amount += curr.outstanding_amount;
                            return acc;
                        }, {});

                        // Convert aggregated data to the format needed for the report
                        const report_data = Object.keys(aggregated_data).map(customer => ({
                            customer: customer,
                            invoiced_amount: aggregated_data[customer].invoiced_amount,
                            paid_amount: aggregated_data[customer].paid_amount,
                            outstanding_amount: aggregated_data[customer].outstanding_amount
                        }));

                        resolve(report_data);
                    } else {
                        reject("Error fetching data.");
                    }
                }
            });
        });
    }
};
