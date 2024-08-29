// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Details", {
    refresh(frm) {
        calculate_totals_in(frm);
        calculate_totals_out(frm);
        calculate_inventory_difference(frm);
    }
});

frappe.ui.form.on('WH Calculation', {
    type: function(frm, cdt, cdn) {
        calculate_volume_and_weight_in(frm, cdt, cdn);
    },
    pieces: function(frm, cdt, cdn) {
        calculate_volume_and_weight_in(frm, cdt, cdn);
    },
    length: function(frm, cdt, cdn) {
        calculate_volume_and_weight_in(frm, cdt, cdn);
    },
    width: function(frm, cdt, cdn) {
        calculate_volume_and_weight_in(frm, cdt, cdn);
    },
    height: function(frm, cdt, cdn) {
        calculate_volume_and_weight_in(frm, cdt, cdn);
    },
    volumecbm: function(frm, cdt, cdn) {
        calculate_totals_in(frm);
    },
    volumetric_weightkg: function(frm, cdt, cdn) {
        calculate_totals_in(frm);
    }
});

frappe.ui.form.on('WH Calculation Out', {
    type: function(frm, cdt, cdn) {
        calculate_volume_and_weight_out(frm, cdt, cdn);
    },
    pieces: function(frm, cdt, cdn) {
        calculate_volume_and_weight_out(frm, cdt, cdn);
    },
    length: function(frm, cdt, cdn) {
        calculate_volume_and_weight_out(frm, cdt, cdn);
    },
    width: function(frm, cdt, cdn) {
        calculate_volume_and_weight_out(frm, cdt, cdn);
    },
    height: function(frm, cdt, cdn) {
        calculate_volume_and_weight_out(frm, cdt, cdn);
    },
    volumecbm: function(frm, cdt, cdn) {
        calculate_totals_out(frm);
    },
    volumetric_weightkg: function(frm, cdt, cdn) {
        calculate_totals_out(frm);
    }
});

function calculate_volume_and_weight_in(frm, cdt, cdn) {
    var row = frappe.get_doc(cdt, cdn); 
    calculate_volume_and_weight_common(frm, cdt, cdn, row);
    calculate_totals_in(frm);
}

function calculate_volume_and_weight_out(frm, cdt, cdn) {
    var row = frappe.get_doc(cdt, cdn); 
    calculate_volume_and_weight_common(frm, cdt, cdn, row);
    calculate_totals_out(frm);
}

function calculate_volume_and_weight_common(frm, cdt, cdn, row) {
    var type = row.type;
    var pieces = parseFloat(row.pieces) || 0;
    var length = parseFloat(row.length) || 0;
    var width = parseFloat(row.width) || 0;
    var height = parseFloat(row.height) || 0;
    var volumecbm = 0;
    var volumetric_weightkg = 0;

    if (type && pieces && width && height) {
        if (type === "Drum") {
            var radius = width / 2 / 100;  
            volumecbm = Math.PI * Math.pow(radius, 2) * (height / 100) * pieces; 
        } else {
            volumecbm = (length / 100) * (width / 100) * (height / 100) * pieces; 
        }

        var volumetric_factor = 167; 
        volumetric_weightkg = volumecbm * volumetric_factor;

        frappe.model.set_value(cdt, cdn, 'volumecbm', volumecbm.toFixed(2));
        frappe.model.set_value(cdt, cdn, 'volumetric_weightkg', volumetric_weightkg.toFixed(2));
    } else {
        frappe.model.set_value(cdt, cdn, 'volumecbm', 0);
        frappe.model.set_value(cdt, cdn, 'volumetric_weightkg', 0);
    }
}

function calculate_totals_in(frm) {
    var total_pieces_in = 0;
    var total_volumecbm_in = 0;
    var total_volumetric_weightkg_in = 0;

    $.each(frm.doc.table_xewa || [], function(i, row) {
        total_pieces_in += parseFloat(row.pieces) || 0;
        total_volumecbm_in += parseFloat(row.volumecbm) || 0;
        total_volumetric_weightkg_in += parseFloat(row.volumetric_weightkg) || 0;
    });

    frm.set_value('number_of_packages', total_pieces_in);
    frm.set_value('volumecbm', total_volumecbm_in.toFixed(2));
    frm.set_value('volumetric_weightkg', total_volumetric_weightkg_in.toFixed(2));

    frm.refresh_fields(['number_of_packages', 'volumecbm', 'volumetric_weightkg']); 

    calculate_inventory_difference(frm);
}

function calculate_totals_out(frm) {
    var total_pieces_out = 0;
    var total_volumecbm_out = 0;
    var total_volumetric_weightkg_out = 0;

    $.each(frm.doc.table_ywnt || [], function(i, row) {
        total_pieces_out += parseFloat(row.pieces) || 0;
        total_volumecbm_out += parseFloat(row.volumecbm) || 0;
        total_volumetric_weightkg_out += parseFloat(row.volumetric_weightkg) || 0;
    });

    frm.set_value('number_of_packages_out', total_pieces_out);
    frm.set_value('volumecbmout', total_volumecbm_out.toFixed(2));
    frm.set_value('volumetric_weightkgout', total_volumetric_weightkg_out.toFixed(2));

    frm.refresh_fields(['number_of_packages_out', 'volumecbmout', 'volumetric_weightkgout']); 

    calculate_inventory_difference(frm);
}

function calculate_inventory_difference(frm) {
    var total_pieces_in = parseFloat(frm.doc.number_of_packages) || 0;
    var total_pieces_out = parseFloat(frm.doc.number_of_packages_out) || 0;
    var total_volumecbm_in = parseFloat(frm.doc.volumecbm) || 0;
    var total_volumecbm_out = parseFloat(frm.doc.volumecbmout) || 0;
    var total_volumetric_weightkg_in = parseFloat(frm.doc.volumetric_weightkg) || 0;
    var total_volumetric_weightkg_out = parseFloat(frm.doc.volumetric_weightkgout) || 0;

    var difference_pieces = total_pieces_in - total_pieces_out;
    var difference_volumecbm = total_volumecbm_in - total_volumecbm_out;
    var difference_volumetric_weightkg = total_volumetric_weightkg_in - total_volumetric_weightkg_out;

    frm.set_value('total_number_of_packages', difference_pieces);
    frm.set_value('total_volumecbm', difference_volumecbm.toFixed(2));
    frm.set_value('total_volumetric_weightkg', difference_volumetric_weightkg.toFixed(2));

    frm.refresh_fields(['total_number_of_packages', 'total_volumecbm', 'total_volumetric_weightkg']); 
}
