# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

"""Where is this waybill, and how long has it been there.

HSM hand the customer a tracking number and then get asked "which store is it in, is it
in movement, where has it reached". Days elapsed counts from the MOVEMENT date, not from
when the receipt was created -- "if it moved on the 1st and today is the 5th, we get that
it moved on the 1st".
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate



def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Waybill No"), "fieldname": "waybill_no", "fieldtype": "Data", "width": 130},
		{"label": _("Tracking No"), "fieldname": "tracking_no", "fieldtype": "Data", "width": 150},
		{"label": _("Receipt"), "fieldname": "name", "fieldtype": "Link",
		 "options": "Receipt Note", "width": 160},
		{"label": _("Status"), "fieldname": "wms_status", "fieldtype": "Data", "width": 150},
		{"label": _("Customer"), "fieldname": "consignee", "fieldtype": "Link",
		 "options": "Customer", "width": 190},
		{"label": _("Currently At"), "fieldname": "current_warehouse_unit", "fieldtype": "Link",
		 "options": "Warehouse Unit", "width": 130},
		{"label": _("CBM"), "fieldname": "total_cbm", "fieldtype": "Float", "precision": 3,
		 "width": 80},
		{"label": _("Packages"), "fieldname": "total_packages", "fieldtype": "Int", "width": 90},
		{"label": _("Received"), "fieldname": "cons_date", "fieldtype": "Date", "width": 100},
		{"label": _("Moved"), "fieldname": "wms_movement_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Since Movement"), "fieldname": "days_since_movement",
		 "fieldtype": "Int", "width": 160},
		{"label": _("Arrived"), "fieldname": "wms_arrival_date", "fieldtype": "Date", "width": 100},
		{"label": _("Delivered"), "fieldname": "wms_delivery_date", "fieldtype": "Date",
		 "width": 100},
		{"label": _("Movement Job"), "fieldname": "wms_job", "fieldtype": "Link",
		 "options": "Job Details", "width": 120},
	]


def get_data(filters):
	conditions = {"docstatus": 1}

	if filters.get("waybill_no"):
		conditions["waybill_no"] = ["like", f"%{filters.waybill_no}%"]
	if filters.get("tracking_no"):
		conditions["tracking_no"] = ["like", f"%{filters.tracking_no}%"]
	if filters.get("customer"):
		conditions["consignee"] = filters.customer
	if filters.get("wms_status"):
		conditions["wms_status"] = filters.wms_status
	if filters.get("warehouse_unit"):
		conditions["current_warehouse_unit"] = filters.warehouse_unit
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("from_date") and filters.get("to_date"):
		conditions["cons_date"] = ["between", [filters.from_date, filters.to_date]]

	rows = frappe.get_all(
		"Receipt Note",
		filters=conditions,
		fields=[
			"name", "waybill_no", "tracking_no", "wms_status", "consignee",
			"current_warehouse_unit", "total_cbm", "total_packages", "cons_date",
			"wms_movement_date", "wms_arrival_date", "wms_delivery_date", "wms_job",
		],
		order_by="cons_date desc, waybill_no",
	)

	today = getdate(nowdate())
	for row in rows:
		if row.wms_movement_date:
			# Once delivered the clock stops on the delivery date, not today.
			end = getdate(row.wms_delivery_date) if row.wms_delivery_date else today
			row["days_since_movement"] = date_diff(end, getdate(row.wms_movement_date))
		else:
			row["days_since_movement"] = None
		row["total_cbm"] = flt(row.total_cbm)

	return rows
