# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

"""Whose cargo is in which warehouse, and how much space it takes.

HSM: "then we can identify what all is there -- what all customer goods are there."
Per-warehouse totals here reconcile with that Warehouse Unit's occupied_capacity_cbm.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(filters, data)


def get_columns():
	return [
		{"label": _("Warehouse"), "fieldname": "current_warehouse_unit", "fieldtype": "Link",
		 "options": "Warehouse Unit", "width": 140},
		{"label": _("Customer"), "fieldname": "consignee", "fieldtype": "Link",
		 "options": "Customer", "width": 210},
		{"label": _("Waybill No"), "fieldname": "waybill_no", "fieldtype": "Data", "width": 130},
		{"label": _("Receipt"), "fieldname": "name", "fieldtype": "Link",
		 "options": "Receipt Note", "width": 160},
		{"label": _("Cargo Type"), "fieldname": "cargo_type", "fieldtype": "Link",
		 "options": "Cargo Type", "width": 140},
		{"label": _("Disposition"), "fieldname": "disposition", "fieldtype": "Data", "width": 170},
		{"label": _("Packages"), "fieldname": "total_packages", "fieldtype": "Int", "width": 90},
		{"label": _("CBM"), "fieldname": "total_cbm", "fieldtype": "Float", "precision": 3,
		 "width": 90},
		{"label": _("Received"), "fieldname": "cons_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Stored"), "fieldname": "days_stored", "fieldtype": "Int", "width": 110},
	]


def get_data(filters):
	conditions = {
		"docstatus": 1,
		"wms_status": ["in", ["In Warehouse", "Arrived at Destination"]],
	}

	if filters.get("warehouse_unit"):
		conditions["current_warehouse_unit"] = filters.warehouse_unit
	if filters.get("customer"):
		conditions["consignee"] = filters.customer
	if filters.get("cargo_type"):
		conditions["cargo_type"] = filters.cargo_type
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("disposition"):
		conditions["disposition"] = filters.disposition

	rows = frappe.get_all(
		"Receipt Note",
		filters=conditions,
		fields=[
			"name", "waybill_no", "consignee", "current_warehouse_unit", "cargo_type",
			"disposition", "total_packages", "total_cbm", "cons_date",
		],
		order_by="current_warehouse_unit, consignee, cons_date",
	)

	today = getdate(nowdate())
	for row in rows:
		row["days_stored"] = date_diff(today, getdate(row.cons_date)) + 1 if row.cons_date else None
		row["total_cbm"] = flt(row.total_cbm)

	return rows


def get_report_summary(filters, data):
	"""Occupancy against declared capacity, so "is it full" is answerable at a glance."""
	stored_cbm = sum(flt(r.get("total_cbm")) for r in data)

	unit_filters = {}
	if filters.get("warehouse_unit"):
		unit_filters["name"] = filters.warehouse_unit

	units = frappe.get_all(
		"Warehouse Unit",
		filters=unit_filters,
		fields=["name", "total_area_capacity", "total_available_capacity"],
	)
	total_capacity = sum(flt(u.total_area_capacity) for u in units)
	available = sum(flt(u.total_available_capacity) for u in units)
	occupied = total_capacity - available

	summary = [
		{"label": _("Consignments Stored"), "value": len(data), "datatype": "Int"},
		{"label": _("Volume on the Floor (CBM)"), "value": stored_cbm, "datatype": "Float"},
		{"label": _("Declared Capacity (CBM)"), "value": total_capacity, "datatype": "Float"},
		{"label": _("Free (CBM)"), "value": available, "datatype": "Float",
		 "indicator": "Red" if total_capacity and available / total_capacity < 0.1 else "Green"},
	]

	if total_capacity:
		summary.append({
			"label": _("Utilisation"),
			"value": occupied / total_capacity * 100.0,
			"datatype": "Percent",
		})

	return summary
