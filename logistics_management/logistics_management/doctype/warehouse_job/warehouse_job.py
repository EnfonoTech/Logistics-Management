# Copyright (c) 2026, siva and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
import json

class WarehouseJob(Document):
    pass

@frappe.whitelist()
def create_warehouse_job_from_receipts(receipt_notes):
    if isinstance(receipt_notes, str):
        receipt_notes = json.loads(receipt_notes)

    if not receipt_notes:
        frappe.throw("No Receipt Notes selected")

    first_rn = frappe.get_doc("Receipt Note", receipt_notes[0])

    wj = frappe.get_doc({
        "doctype": "Warehouse Job",
        "consignee": first_rn.consignee,
        "status": "Draft"
    })

    total_cbm = 0
    warehouse_unit = None

    for rn_name in receipt_notes:
        rn = frappe.get_doc("Receipt Note", rn_name)

        wj.append("warehouse_job_receipt_note", {
            "receipt_note": rn.name,
            "customer": rn.consignee,
            "warehouse": rn.warehouse_unit,
            "total_cbm": rn.total_cbm,
            "waybill_no": rn.waybill_no
        })

        total_cbm += rn.total_cbm
        warehouse_unit = rn.warehouse_unit

        frappe.db.set_value("Receipt Note", rn.name, "job_status", "Created")

    wj.insert(ignore_permissions=True)
    
    current_capacity = frappe.db.get_value("Warehouse Unit", warehouse_unit, "total_available_capacity") or 0
    frappe.db.set_value("Warehouse Unit", warehouse_unit, "total_available_capacity", current_capacity + total_cbm)

    frappe.db.commit()

    return wj.name
