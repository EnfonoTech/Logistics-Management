# Copyright (c) 2026, siva and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


class WarehouseJob(Document):
	"""Legacy warehouse job. Superseded by Warehouse 3PL's Warehouse Job Record."""

	pass


@frappe.whitelist()
def create_warehouse_job_from_receipts(receipt_notes):
	"""Create one Warehouse Job covering several Receipt Notes for the same consignee.

	Every @frappe.whitelist() is a public HTTP endpoint, so the permission checks below
	are the real gate -- the list-view button that calls this is not.
	"""
	if isinstance(receipt_notes, str):
		receipt_notes = json.loads(receipt_notes)

	receipt_notes = [cstr(n) for n in (receipt_notes or []) if cstr(n)]
	if not receipt_notes:
		frappe.throw(_("No Receipt Notes selected"))

	frappe.has_permission("Warehouse Job", "create", throw=True)
	for rn_name in receipt_notes:
		frappe.has_permission("Receipt Note", "write", doc=rn_name, throw=True)

	rows = frappe.get_all(
		"Receipt Note",
		filters={"name": ["in", receipt_notes]},
		fields=[
			"name",
			"consignee",
			"warehouse_unit",
			"total_cbm",
			"waybill_no",
			"job_status",
			"docstatus",
		],
	)
	found = {r.name for r in rows}
	missing = set(receipt_notes) - found
	if missing:
		frappe.throw(_("Receipt Note(s) not found: {0}").format(", ".join(sorted(missing))))

	# Idempotency. job_status was stamped "Created" but never read back, so calling this
	# twice on the same notes credited the warehouse capacity twice.
	already = [r.name for r in rows if r.job_status == "Created"]
	if already:
		frappe.throw(
			_("A Warehouse Job has already been created for: {0}").format(", ".join(sorted(already)))
		)

	not_submitted = [r.name for r in rows if r.docstatus != 1]
	if not_submitted:
		frappe.throw(
			_("Receipt Note(s) must be submitted first: {0}").format(", ".join(sorted(not_submitted)))
		)

	consignees = {r.consignee for r in rows}
	if len(consignees) > 1:
		frappe.throw(_("All selected Receipt Notes must share the same consignee."))

	units = {r.warehouse_unit for r in rows if r.warehouse_unit}
	if len(units) > 1:
		frappe.throw(_("All selected Receipt Notes must share the same Warehouse Unit."))

	wj = frappe.get_doc({
		"doctype": "Warehouse Job",
		"consignee": rows[0].consignee,
		"status": "Draft",
	})

	total_cbm = 0.0
	for r in rows:
		wj.append("warehouse_job_receipt_note", {
			"receipt_note": r.name,
			"customer": r.consignee,
			"warehouse": r.warehouse_unit,
			"total_cbm": flt(r.total_cbm),
			"waybill_no": r.waybill_no,
		})
		total_cbm += flt(r.total_cbm)

	wj.insert()
	wj.submit()

	for r in rows:
		frappe.db.set_value("Receipt Note", r.name, "job_status", "Created")

	warehouse_unit = next(iter(units), None)
	if warehouse_unit and total_cbm:
		current = flt(
			frappe.db.get_value(
				"Warehouse Unit", warehouse_unit, "total_available_capacity", for_update=True
			)
		)
		frappe.db.set_value(
			"Warehouse Unit", warehouse_unit, "total_available_capacity", current + total_cbm
		)

	# No frappe.db.commit() here on purpose. Committing mid-request defeated the
	# rollback, so a later failure left a submitted job and a mutated capacity behind.
	return wj.name
