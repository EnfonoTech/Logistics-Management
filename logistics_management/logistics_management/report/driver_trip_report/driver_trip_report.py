# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

"""What each driver carried, and when.

A trip and a delivery are not the same number and HSM asked for the trip one. A driver who
takes three waybills out in the same truck on the same morning has made ONE trip and THREE
deliveries -- counting rows would triple his day. So a trip here is a distinct
(driver, vehicle, delivery date), and both figures are reported side by side rather than
one standing in for the other.

Scope is deliberately the WMS delivery path only: rows come from Waybill Console, so the
491 older PODs that predate this module, which carry a typed-in driver name and no link to
anything, are not in it. A report that silently mixed free text with masters would give a
per-driver total nobody could reconcile.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_report_summary(data)


def get_columns():
	return [
		{"label": _("Delivery Date"), "fieldname": "wms_delivery_date", "fieldtype": "Date",
		 "width": 110},
		{"label": _("Driver"), "fieldname": "wms_driver", "fieldtype": "Link",
		 "options": "Driver", "width": 120},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 170},
		{"label": _("Vehicle"), "fieldname": "wms_vehicle", "fieldtype": "Link",
		 "options": "Vehicle", "width": 120},
		{"label": _("Waybill"), "fieldname": "name", "fieldtype": "Link",
		 "options": "Waybill Console", "width": 130},
		{"label": _("Waybill No"), "fieldname": "waybill_no", "fieldtype": "Data", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link",
		 "options": "Customer", "width": 190},
		{"label": _("Job"), "fieldname": "job_details", "fieldtype": "Link",
		 "options": "Job Details", "width": 120},
		{"label": _("Container"), "fieldname": "container_no", "fieldtype": "Data", "width": 120},
		{"label": _("Packages"), "fieldname": "total_packages", "fieldtype": "Int", "width": 90},
		{"label": _("CBM"), "fieldname": "total_cbm", "fieldtype": "Float", "precision": 3,
		 "width": 90},
		{"label": _("Mode"), "fieldname": "wms_delivery_mode", "fieldtype": "Data", "width": 100},
		{"label": _("Collected By"), "fieldname": "wms_collected_by", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Delivered From"), "fieldname": "destination", "fieldtype": "Link",
		 "options": "Warehouse Unit", "width": 130},
		{"label": _("POD"), "fieldname": "pod", "fieldtype": "Link", "options": "POD",
		 "width": 100},
		{"label": _("Signed POD"), "fieldname": "pod_received", "fieldtype": "Check", "width": 100},
	]


def get_data(filters):
	wc = frappe.qb.DocType("Waybill Console")
	jd = frappe.qb.DocType("Job Details")
	rn = frappe.qb.DocType("Receipt Note")
	dr = frappe.qb.DocType("Driver")
	pod = frappe.qb.DocType("POD")

	query = (
		frappe.qb.from_(wc)
		.left_join(jd).on(wc.job_details == jd.name)
		.left_join(rn).on(wc.wms_receipt_note == rn.name)
		.left_join(dr).on(wc.wms_driver == dr.name)
		.left_join(pod).on(pod.waybill_console == wc.name)
		.select(
			wc.name, wc.waybill_no, wc.customer, wc.job_details,
			wc.wms_delivery_date, wc.wms_delivery_mode, wc.wms_collected_by,
			wc.wms_driver, wc.wms_vehicle,
			dr.full_name.as_("driver_name"),
			jd.container_no,
			jd.wms_destination_warehouse.as_("destination"),
			rn.total_cbm, rn.total_packages,
			pod.name.as_("pod"), pod.wms_pod_received.as_("pod_received"),
		)
		.where(wc.wms_delivered == 1)
		.orderby(wc.wms_delivery_date)
		.orderby(wc.wms_driver)
		.orderby(wc.waybill_no)
	)

	if filters.get("from_date"):
		query = query.where(wc.wms_delivery_date >= getdate(filters.from_date))
	if filters.get("to_date"):
		query = query.where(wc.wms_delivery_date <= getdate(filters.to_date))
	if filters.get("driver"):
		query = query.where(wc.wms_driver == filters.driver)
	if filters.get("vehicle"):
		query = query.where(wc.wms_vehicle == filters.vehicle)
	if filters.get("customer"):
		query = query.where(wc.customer == filters.customer)
	if filters.get("delivery_mode"):
		query = query.where(wc.wms_delivery_mode == filters.delivery_mode)
	if filters.get("company"):
		query = query.where(jd.company == filters.company)
	if filters.get("only_undriven"):
		# Finding the deliveries nobody recorded a driver against is the whole point of
		# chasing the backlog, so it is a filter and not something to page through.
		query = query.where((wc.wms_driver == "") | wc.wms_driver.isnull())

	return query.run(as_dict=True)


def count_trips(data):
	"""One trip is one driver, in one vehicle, on one date -- however many waybills rode in it."""
	return len({
		(row.get("wms_driver"), row.get("wms_vehicle"), str(row.get("wms_delivery_date")))
		for row in data
		if row.get("wms_driver")
	})


def get_report_summary(data):
	if not data:
		return None

	driven = [r for r in data if r.get("wms_driver")]
	return [
		{"label": _("Trips"), "value": count_trips(data), "datatype": "Int",
		 "indicator": "Blue"},
		{"label": _("Deliveries"), "value": len(data), "datatype": "Int"},
		{"label": _("Drivers"), "value": len({r["wms_driver"] for r in driven}), "datatype": "Int"},
		{"label": _("Total CBM"), "value": flt(sum(flt(r.get("total_cbm")) for r in data), 3),
		 "datatype": "Float"},
		{"label": _("No Driver Recorded"), "value": len(data) - len(driven), "datatype": "Int",
		 "indicator": "Orange" if len(driven) < len(data) else "Green"},
	]


def get_chart(data):
	"""Trips per driver -- the one number HSM asked for, as a picture."""
	trips = {}
	for row in data:
		if not row.get("wms_driver"):
			continue
		key = row.get("driver_name") or row["wms_driver"]
		trips.setdefault(key, set()).add(
			(row.get("wms_vehicle"), str(row.get("wms_delivery_date")))
		)
	if not trips:
		return None

	ordered = sorted(trips.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
	return {
		"data": {
			"labels": [name for name, _runs in ordered],
			"datasets": [{"name": _("Trips"), "values": [len(runs) for _name, runs in ordered]}],
		},
		"type": "bar",
		"colors": ["#449cf0"],
	}
