// Copyright (c) 2026, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Waybill Tracking"] = {
    filters: [
        { fieldname: "waybill_no", label: __("Waybill No"), fieldtype: "Data" },
        { fieldname: "tracking_no", label: __("Tracking No"), fieldtype: "Data" },
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        {
            fieldname: "wms_status",
            label: __("Status"),
            fieldtype: "Select",
            options: ["", "In Warehouse", "In Movement", "Arrived at Destination", "Delivered"].join("\n"),
        },
        {
            fieldname: "warehouse_unit",
            label: __("Currently At"),
            fieldtype: "Link",
            options: "Warehouse Unit",
        },
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        { fieldname: "from_date", label: __("Received From"), fieldtype: "Date" },
        { fieldname: "to_date", label: __("Received To"), fieldtype: "Date" },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "wms_status" && data && data.wms_status) {
            const colours = {
                "In Warehouse": "blue",
                "In Movement": "orange",
                "Arrived at Destination": "purple",
                Delivered: "green",
            };
            const colour = colours[data.wms_status] || "gray";
            value = `<span class="indicator-pill ${colour}">${frappe.utils.escape_html(
                data.wms_status
            )}</span>`;
        }

        // A waybill sitting in movement for a fortnight is the thing an operator needs
        // to spot before the customer rings about it.
        if (
            column.fieldname === "days_since_movement" &&
            data &&
            data.wms_status === "In Movement" &&
            cint(data.days_since_movement) > 14
        ) {
            value = `<span style="color: var(--red-600); font-weight: 600;">${value}</span>`;
        }

        return value;
    },
};
