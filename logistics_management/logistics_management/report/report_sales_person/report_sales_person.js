
// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

frappe.query_reports["Report-Sales Person"] = {
    "filters": [
        {
            "fieldname": "job_details",
            "label": __("Job Details"),
            "fieldtype": "Link",
            "options": "Job Details",
            "reqd": 0,
            "default": "",
            "width": "80"
        },
        {
            "fieldname": "sales_person",
            "label": __("Sales Person"),
            "fieldtype": "Link",
            "options": "Sales Person",
            "reqd": 0,
            "default": "",
            "width": "80"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 0,
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "width": "80"
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 0,
            "default": frappe.datetime.get_today(),
            "width": "80"
        }
    ],

    "onload": function(report) {
        report.page.add_inner_button(__('Refresh Data'), function() {
            report.refresh();
        });
    },

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "profit_and_loss") {
            if (data.profit_and_loss < 0) {
                value = `<span style="color:red">${value}</span>`;
            } else {
                value = `<span style="color:green">${value}</span>`;
            }
        }
        if (column.fieldname == "sales_outstanding_amount") {
            if (flt(value) === 0) {
                value = `<span style="color:black">${value}</span>`;
            } else {
                value = `<span style="color:green">${value}</span>`;
            }
        }
        if (column.fieldname == "purchase_outstanding_amount") {
            if (flt(value) === 0) {
                value = `<span style="color:black">${value}</span>`;
            } else {
                value = `<span style="color:orange">${value}</span>`;
            }
        }
        return value;
    }
};
