// Copyright (c) 2026, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Driver Trip Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
            reqd: 1,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_end(),
            reqd: 1,
        },
        {
            fieldname: "driver",
            label: __("Driver"),
            fieldtype: "Link",
            options: "Driver",
        },
        {
            fieldname: "vehicle",
            label: __("Vehicle"),
            fieldtype: "Link",
            options: "Vehicle",
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
        },
        {
            fieldname: "delivery_mode",
            label: __("Delivery Mode"),
            fieldtype: "Select",
            options: ["", "Delivery", "Collection"],
        },
        {
            fieldname: "only_undriven",
            label: __("Only deliveries with no driver"),
            fieldtype: "Check",
            default: 0,
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        // A delivery with no driver is the row worth chasing, so it is the one that stands out.
        if (column.fieldname === "driver_name" && data && !data.wms_driver) {
            value = `<span class="text-muted">${__("Not recorded")}</span>`;
        }
        return value;
    },
};
