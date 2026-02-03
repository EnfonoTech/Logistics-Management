// Copyright (c) 2026, siva and contributors
// For license information, please see license.txt

frappe.ui.form.on('Package Details', {
    length(frm, cdt, cdn) {
        calculate_cbm_and_total(frm, cdt, cdn);
    },
    width(frm, cdt, cdn) {
        calculate_cbm_and_total(frm, cdt, cdn);
    },
    height(frm, cdt, cdn) {
        calculate_cbm_and_total(frm, cdt, cdn);
    },
    cbm(frm) {
        calculate_total_cbm(frm);
    }
});

function calculate_cbm_and_total(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let length = flt(row.length);
    let width  = flt(row.width);
    let height = flt(row.height);

    if (length > 0 && width > 0 && height > 0) {
        let cbm = (length * width * height) / 1000000;
        frappe.model.set_value(cdt, cdn, "cbm", cbm);
    } else {
        frappe.model.set_value(cdt, cdn, "cbm", 0);
    }

    calculate_total_cbm(frm);
}

function calculate_total_cbm(frm) {
    let total = 0;

    (frm.doc.package_details || []).forEach(row => {
        total += flt(row.cbm);
    });

    frm.set_value("total_cbm", total);
}
