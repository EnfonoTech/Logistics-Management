frappe.query_reports["Job Details Report"] = {
    "filters": [
        {
            "fieldname": "job_details",
            "label": __("Job Details"),
            "fieldtype": "Link",
            "options": "Job Details",
            "reqd": 0,
            "default": "",
            "width": "80",
            // "get_data": function(txt) {
            //     return frappe.db.get_link_options('Job Details', txt);
            // }
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
