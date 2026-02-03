# Copyright (c) 2026, siva and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ReceiptNote(Document):
    pass

def on_submit(doc, method):
    """
    Reduce total_available_capacity in the linked Warehouse Unit
    based on total CBM of items in the Receipt Note
    """   
    if not doc.warehouse_unit:
        return  
   
    total_cbm = sum([item.cbm for item in doc.package_details])
   
    warehouse = frappe.get_doc("Warehouse Unit", doc.warehouse_unit)
    new_capacity = warehouse.total_available_capacity - total_cbm

    if new_capacity < 0:
        frappe.throw(f"Not enough available capacity in warehouse {warehouse.name}.")
   
    frappe.db.set_value("Warehouse Unit", warehouse.name, "total_available_capacity", new_capacity)


