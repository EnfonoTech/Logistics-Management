// Copyright (c) 2024, siva and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Details", {
    refresh(frm) {
        frm.fields_dict['section_break_eizt'].wrapper.css('background-color', 'antiquewhite');
        frm.fields_dict['section_break_onyq'].wrapper.css('background-color', 'antiquewhite');
        frm.fields_dict['summary_section'].wrapper.css('background-color', 'cadetblue');

        calculate_totals_in(frm);
        calculate_totals_out(frm);
        calculate_inventory_difference(frm);

        frm.add_custom_button(__('Generate Rent'), function() {
            if (!frm.rent_generation_confirmed) {
                frappe.msgprint(__('Click the Generate Rent button again to confirm.'));
                frm.rent_generation_confirmed = true; 
            } else {
                generate_rent(frm);
                frm.rent_generation_confirmed = false; 
            }
        });
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

function generate_rent(frm) {
    var start_date = frm.doc.rent_start_date;
    var end_date = frm.doc.rent_end_date;
    var rent_per_cbm = parseFloat(frm.doc.rent_per_cbm) || 0;

    if (!start_date || !end_date || !rent_per_cbm) {
        frappe.msgprint(__('Please provide Rent Start Date, Rent End Date, and Rent per CBM'));
        return;
    }

    var start = new Date(start_date);
    var end = new Date(end_date);
    var timeDiff = end - start;
    var daysDiff = timeDiff / (1000 * 3600 * 24);

    if (daysDiff < 0) {
        frappe.msgprint(__('Rent End Date must be after Rent Start Date'));
        return;
    }

    var last_end_date = get_last_end_date(frm);

    if (last_end_date && start <= new Date(last_end_date)) {
        frappe.msgprint(__('Rent Start Date must be after the last entry\'s end date.'));
        return;
    }

    if (is_date_range_conflicting(frm, start_date, end_date)) {
        frappe.msgprint(__('Cannot generate rent because the date range overlaps with existing out dates.'));
        return;
    }

    var cbm_data = calculate_total_cbm_by_type(frm, start_date, end_date);

    var has_data = Object.keys(cbm_data).some(function(type) {
        return cbm_data[type] > 0;
    });

    if (!has_data) {
        frappe.msgprint(__('No data found during the selected period.'));
        return; 
    }

    var new_rows = [];

    Object.keys(cbm_data).forEach(function(type) {
        var total_cbm = cbm_data[type];
        var rent = daysDiff * rent_per_cbm * total_cbm;

        var new_row = {
            start_date: start_date,
            end_date: end_date,
            type: type,
            rent_per_cbm: rent_per_cbm,
            cbm: total_cbm,
            rent: rent
        };

        new_rows.push(new_row);
    });

    if (new_rows.length > 0) {
        new_rows.forEach(function(row) {
            var new_row = frm.add_child('table_yvty');
            Object.assign(new_row, row);
        });

        frm.refresh_field('table_yvty');
        frappe.msgprint(__('Rent rows generated successfully.'));
    }
}

function get_last_end_date(frm) {
    var last_end_date = null;

    $.each(frm.doc.table_yvty || [], function(i, row) {
        var current_end_date = new Date(row.end_date);
        if (!last_end_date || current_end_date > new Date(last_end_date)) {
            last_end_date = row.end_date;
        }
    });

    return last_end_date;
}

function is_date_range_conflicting(frm, start_date, end_date) {
    var conflict_found = false;
    var rent_start = new Date(start_date);
    var rent_end = new Date(end_date);

    $.each(frm.doc.table_ywnt || [], function(i, row) {
        var out_date = new Date(row.out_date);

        if (out_date > rent_start && out_date < rent_end) {
            conflict_found = true;
            return false; 
        }
    });

    return conflict_found;
}





function calculate_total_cbm_by_type(frm, start_date, end_date) {
    var cbm_data = {};

    // Calculate CBM from IN table based on the rent_start_date
    // $.each(frm.doc.table_xewa || [], function(i, row) {
    //     var row_date = new Date(row.in_date);
    //     var type = row.type;

    //     if (row_date >= new Date(start_date) && row_date <= new Date(end_date)) {
    //         if (!cbm_data[type]) {
    //             cbm_data[type] = 0;
    //         }
    //         cbm_data[type] += parseFloat(row.volumecbm) || 0;
    //     }
    // });

    $.each(frm.doc.table_ywnt || [], function(i, row) {
        var row_date = new Date(row.out_date);
        var type = row.type;

        if (row_date >= new Date(start_date) && row_date <= new Date(end_date)) {
            if (!cbm_data[type]) {
                cbm_data[type] = 0;
            }
            cbm_data[type] += parseFloat(row.volumecbm) || 0;
        }
    });

    return cbm_data; 
}

