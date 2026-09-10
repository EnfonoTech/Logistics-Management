// Copyright (c) 2026, siva and contributors
// For license information, please see license.txt

// Row CBM is length x width x height / 1e6 x qty. The same arithmetic lives in
// receipt_note.py so an import or a server-side insert produces identical figures.
const CBM_PER_CUBIC_CM = 1000000;

frappe.ui.form.on("Receipt Note", {
    onload(frm) {
        // The company field carries no `default` in the DocType: ":Company" is a
        // child-row idiom that breaks frappe.new_doc() on a parent. ERPNext fills it
        // from the user's default here instead, same as Sales Invoice does.
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company"));
        }
    },

    refresh(frm) {
        show_warehouse_space(frm);
        show_status_indicator(frm);
    },

    warehouse_unit(frm) {
        show_warehouse_space(frm, { fetch: true });
    },

    package_details_add(frm) {
        recalculate(frm);
    },
});

frappe.ui.form.on("Package Details", {
    qty(frm, cdt, cdn) {
        recalculate_row(frm, cdt, cdn);
    },
    length(frm, cdt, cdn) {
        recalculate_row(frm, cdt, cdn);
    },
    width(frm, cdt, cdn) {
        recalculate_row(frm, cdt, cdn);
    },
    height(frm, cdt, cdn) {
        recalculate_row(frm, cdt, cdn);
    },
    package_details_remove(frm) {
        recalculate(frm);
    },
});

function recalculate_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const qty = cint(row.qty) || 1;
    const l = flt(row.length);
    const w = flt(row.width);
    const h = flt(row.height);

    const unit_cbm = l > 0 && w > 0 && h > 0 ? (l * w * h) / CBM_PER_CUBIC_CM : 0;
    frappe.model.set_value(cdt, cdn, "cbm", unit_cbm * qty);
    recalculate(frm);
}

function recalculate(frm) {
    let total_cbm = 0;
    let total_packages = 0;

    (frm.doc.package_details || []).forEach((row) => {
        total_cbm += flt(row.cbm);
        total_packages += cint(row.qty) || 1;
    });

    frm.set_value("total_cbm", total_cbm);
    frm.set_value("total_packages", total_packages);
    show_warehouse_space(frm);
}

function show_warehouse_space(frm, { fetch = false } = {}) {
    if (!frm.doc.warehouse_unit) {
        frm.set_value("wh_utilisation_pct", 0);
        frm.dashboard.clear_headline();
        return;
    }

    // fetch_from fills the two CBM figures on link change, but a warehouse whose space
    // moved since this form opened would show a stale number -- so on an explicit
    // warehouse change we read it live. This is the "show me the space before I start
    // typing" ask.
    const render = (space) => {
        frm.set_value("wh_total_cbm", space.total_cbm);
        frm.set_value("wh_available_cbm", space.available_cbm);
        frm.set_value("wh_utilisation_pct", space.utilisation_pct);
        headline(frm, space);
    };

    if (fetch) {
        frappe.call({
            method: "logistics_management.wms.capacity.get_capacity_for_display",
            args: { warehouse_unit: frm.doc.warehouse_unit },
            callback: (r) => r.message && render(r.message),
        });
        return;
    }

    const total = flt(frm.doc.wh_total_cbm);
    const available = flt(frm.doc.wh_available_cbm);
    const occupied = total - available;
    headline(frm, {
        total_cbm: total,
        available_cbm: available,
        occupied_cbm: occupied,
        utilisation_pct: total ? (occupied / total) * 100 : 0,
    });
}

function headline(frm, space) {
    if (!flt(space.total_cbm)) {
        frm.dashboard.set_headline(
            __("{0} has no capacity set. Enter its total capacity in CBM to track space.", [
                frm.doc.warehouse_unit,
            ]),
            "orange"
        );
        return;
    }

    const needed = flt(frm.doc.total_cbm);
    const fits = needed <= flt(space.available_cbm);
    const colour = !fits ? "red" : space.utilisation_pct > 85 ? "orange" : "blue";

    let msg = __("{0}: {1} CBM free of {2} CBM ({3}% used)", [
        frm.doc.warehouse_unit,
        format_number(space.available_cbm, null, 2),
        format_number(space.total_cbm, null, 2),
        format_number(space.utilisation_pct, null, 1),
    ]);

    if (needed > 0 && !fits) {
        msg += " — " + __("this receipt needs {0} CBM and will not fit", [
            format_number(needed, null, 2),
        ]);
    }

    frm.dashboard.set_headline(msg, colour);
}

function show_status_indicator(frm) {
    if (frm.doc.docstatus !== 1 || !frm.doc.wms_status) return;

    const colours = {
        "In Warehouse": "blue",
        "In Movement": "orange",
        "Arrived at Destination": "purple",
        Delivered: "green",
    };
    frm.page.set_indicator(__(frm.doc.wms_status), colours[frm.doc.wms_status] || "gray");

    if (frm.doc.wms_job) {
        frm.add_custom_button(__("Movement Job"), () =>
            frappe.set_route("Form", "Job Details", frm.doc.wms_job)
        );
    }
}
