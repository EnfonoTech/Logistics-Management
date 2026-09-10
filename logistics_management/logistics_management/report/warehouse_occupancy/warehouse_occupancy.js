// Copyright (c) 2026, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Warehouse Occupancy"] = {
    filters: [
        {
            fieldname: "warehouse_unit",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse Unit",
        },
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        {
            fieldname: "cargo_type",
            label: __("Cargo Type"),
            fieldtype: "Link",
            options: "Cargo Type",
        },
        {
            fieldname: "disposition",
            label: __("Disposition"),
            fieldtype: "Select",
            options: ["", "Move to Other Warehouse", "Store at Same Warehouse"].join("\n"),
        },
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
    ],
};
