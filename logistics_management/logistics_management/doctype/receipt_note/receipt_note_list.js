frappe.listview_settings['Receipt Note'] = {
    add_fields: ["consignee"],

    onload: function(listview) {
   
        const create_btn = listview.page.add_inner_button(__('Create Warehouse Job'), function() {
            const selected = listview.get_checked_items();
            if (!selected.length) return;

            const receipt_notes = selected.map(d => d.name);

            frappe.call({
                method: "logistics_management.logistics_management.doctype.warehouse_job.warehouse_job.create_warehouse_job_from_receipts",
                args: { receipt_notes },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __('Warehouse Job Created!'), indicator: 'green' });
                        frappe.set_route('Form', 'Warehouse Job', r.message);
                    }
                }
            });
        });

        create_btn.hide();
       
        listview.page.wrapper.on('change', '.list-row-checkbox', function() {
            const selected = listview.get_checked_items();
            if (selected.length === 0) {
                create_btn.hide();
                return;
            }
           
            const consignee = selected[0].consignee;
            const same = selected.every(d => d.consignee === consignee);
            same ? create_btn.show() : create_btn.hide();
        });

    }
};
