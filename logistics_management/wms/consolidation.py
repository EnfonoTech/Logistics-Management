"""Movement: turn a hand-picked set of Receipt Notes into one consolidation job.

The whole point of a console job is that it holds MANY customers. HSM collect from ten
to twenty of them, load one container and move it as a single shipment, so the cost is
a single cost. The job header therefore carries the company, not a customer, and the
customers live in the console rows.

The superseded create_warehouse_job_from_receipts() did the opposite -- it threw
"All selected Receipt Notes must share the same consignee" -- and it built a Warehouse
Job, a DocType with no rows that nothing invoices from. This targets Job Details with
job_type CONSOLE, which is what the 1,412 live jobs, the Sales Invoice link and the POD
link all use.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, nowdate

from logistics_management.wms import capacity, settings

MOVEABLE_DISPOSITION = "Move to Other Warehouse"


@frappe.whitelist()
def create_console_job_from_receipts(
	receipt_notes,
	mode_of_transport=None,
	movement_date=None,
	destination_warehouse=None,
	shipment_mode=None,
):
	"""Create one CONSOLE Job Details covering several Receipt Notes, any mix of customers.

	Every @frappe.whitelist() is a public HTTP endpoint. The permission checks below are
	the real gate -- the list-view button that calls this is not.
	"""
	receipts = _validated_receipts(receipt_notes)
	origin = receipts[0].warehouse_unit
	company = receipts[0].company

	if destination_warehouse and destination_warehouse == origin:
		frappe.throw(_("Destination warehouse cannot be the same as the origin, {0}.").format(origin))

	movement_date = getdate(movement_date or nowdate())
	mode_of_transport = mode_of_transport or _default_transport(origin)

	packages = _package_summary([r.name for r in receipts])

	job = frappe.new_doc("Job Details")
	job.job_type = "CONSOLE"
	job.company = company
	job.mode_of_transport = mode_of_transport
	job.shipment_mode = shipment_mode or settings.get("default_shipment_mode")
	job.date = movement_date
	job.etd = movement_date
	job.place_of_receipt = origin
	job.place_of_delivery = destination_warehouse or ""
	job.wms_origin_warehouse = origin
	job.wms_destination_warehouse = destination_warehouse
	job.wms_movement_date = movement_date
	job.job_status = "In Progress"
	# job_id is a Link to Customer despite the name. A console job has no single
	# customer, so it is deliberately left blank -- its only consumers display it, and
	# the per-customer figures come off the console rows.

	total_cbm = 0.0
	for r in receipts:
		pkg = packages.get(r.name, frappe._dict(qty=0, types=""))
		job.append(
			"console_shipment",
			{
				"cn": r.waybill_no,
				"customer": r.consignee,
				"nopkgs": cstr(pkg.qty),
				"pkg_type": pkg.types,
				"mode_of_delivery": r.receipt_mode or "",
				"shipper_name": r.shipper_name or r.shipper or "",
				"remarks": r.name,
			},
		)
		total_cbm += flt(r.total_cbm)

	job.volume = total_cbm
	job.number_of_packages = cstr(sum(cint(packages.get(r.name, {}).get("qty", 0)) for r in receipts))
	job.insert()

	consoles = [_ensure_waybill_console(r, job, packages.get(r.name)) for r in receipts]

	for r in receipts:
		frappe.db.set_value(
			"Receipt Note",
			r.name,
			{
				"job_status": "Created",
				"wms_status": "In Movement",
				"wms_job": job.name,
				"wms_movement_date": movement_date,
				"current_warehouse_unit": None,
			},
			update_modified=False,
		)

	# The origin warehouse gives its space back the moment the container leaves. The
	# destination takes it on arrival, not now -- the cargo is in transit in between.
	capacity.release(origin, total_cbm, context=_("movement {0}").format(job.name))

	# No frappe.db.commit() here on purpose: committing mid-request would defeat the
	# rollback, so a later failure would leave a job and a mutated capacity behind.
	return frappe._dict(job=job.name, waybill_consoles=consoles, total_cbm=total_cbm)


def _validated_receipts(receipt_notes):
	"""Load the selected receipts and refuse every state that must not be jobbed."""
	if isinstance(receipt_notes, str):
		receipt_notes = json.loads(receipt_notes)

	names = [cstr(n) for n in (receipt_notes or []) if cstr(n)]
	if not names:
		frappe.throw(_("No Receipt Notes selected"))

	frappe.has_permission("Job Details", "create", throw=True)
	for name in names:
		frappe.has_permission("Receipt Note", "write", doc=name, throw=True)

	rows = frappe.get_all(
		"Receipt Note",
		filters={"name": ["in", names]},
		fields=[
			"name", "waybill_no", "consignee", "warehouse_unit", "company", "total_cbm",
			"job_status", "docstatus", "disposition", "receipt_mode", "shipper",
			"shipper_name", "wms_status",
		],
	)

	missing = set(names) - {r.name for r in rows}
	if missing:
		frappe.throw(_("Receipt Note(s) not found: {0}").format(", ".join(sorted(missing))))

	not_submitted = sorted(r.name for r in rows if r.docstatus != 1)
	if not_submitted:
		frappe.throw(_("Receipt Note(s) must be submitted first: {0}").format(", ".join(not_submitted)))

	# job_status was previously stamped "Created" and never read back, so calling the
	# action twice on the same notes credited the origin warehouse twice.
	already = sorted(r.name for r in rows if r.job_status == "Created")
	if already:
		frappe.throw(_("A job has already been created for: {0}").format(", ".join(already)))

	stored = sorted(r.name for r in rows if r.disposition and r.disposition != MOVEABLE_DISPOSITION)
	if stored:
		frappe.throw(
			_("These Receipt Notes are marked for storage at the same warehouse, not for movement:"
			  " {0}. Change the disposition first if they are to be moved.").format(", ".join(stored))
		)

	no_consignee = sorted(r.name for r in rows if not r.consignee)
	if no_consignee:
		frappe.throw(_("Receipt Note(s) have no consignee, so they cannot be invoiced: {0}").format(
			", ".join(no_consignee)))

	origins = {r.warehouse_unit for r in rows if r.warehouse_unit}
	if len(origins) > 1:
		frappe.throw(
			_("A console ships from one origin. These Receipt Notes span {0} warehouses: {1}.").format(
				len(origins), ", ".join(sorted(origins))
			)
		)
	if not origins:
		frappe.throw(_("Receipt Note(s) have no warehouse set."))

	companies = {r.company for r in rows if r.company}
	if len(companies) > 1:
		frappe.throw(
			_("These Receipt Notes belong to {0} different companies: {1}."
			  " One job cannot span companies.").format(len(companies), ", ".join(sorted(companies)))
		)
	if not companies:
		frappe.throw(_("Receipt Note(s) have no company set."))

	# NOTE: there is deliberately no check that the consignees match. One console job
	# holding many customers is the requirement, stated three times on 2026-09-05.
	return rows


def _package_summary(receipt_names):
	"""Total package count and the distinct package types per receipt, in one query."""
	summary = {}
	if not receipt_names:
		return summary

	rows = frappe.get_all(
		"Package Details",
		filters={"parent": ["in", receipt_names], "parenttype": "Receipt Note"},
		fields=["parent", "type", "qty"],
	)
	for row in rows:
		entry = summary.setdefault(row.parent, frappe._dict(qty=0, type_set=set()))
		# Whole packages. flt here made a waybill read "7.0 packages".
		entry.qty += cint(row.qty) or 1
		if row.type:
			entry.type_set.add(row.type)

	for entry in summary.values():
		entry.types = ", ".join(sorted(entry.type_set))
		entry.pop("type_set", None)

	return summary


def _ensure_waybill_console(receipt, job, pkg):
	"""One Waybill Console per receipt, created from the receipt rather than by hand.

	If one already exists for this waybill number -- HSM typed them manually before this
	existed -- it is linked to the job instead of being duplicated. waybill_no is unique,
	so a blind insert would fail on exactly the records most likely to be there already.
	"""
	pkg = pkg or frappe._dict(qty=0, types="")
	existing = frappe.db.exists("Waybill Console", {"waybill_no": receipt.waybill_no})

	values = {
		"customer": receipt.consignee,
		"shipper": receipt.shipper_name or receipt.shipper or "",
		"no_of_packages": cstr(cint(pkg.get("qty")) or ""),
		"volume": cstr(flt(receipt.total_cbm)),
		"job_details": job.name,
		"wms_receipt_note": receipt.name,
		"wms_status": "In Movement",
	}

	if existing:
		frappe.db.set_value("Waybill Console", existing, values, update_modified=False)
		frappe.db.set_value("Receipt Note", receipt.name, "wms_waybill_console", existing,
		                    update_modified=False)
		return existing

	console = frappe.new_doc("Waybill Console")
	console.waybill_no = receipt.waybill_no
	console.update(values)
	console.insert()
	frappe.db.set_value("Receipt Note", receipt.name, "wms_waybill_console", console.name,
	                    update_modified=False)
	return console.name


def _default_transport(warehouse_unit):
	"""The origin warehouse's own default -- configuration, not a guess from its name."""
	return (
		frappe.db.get_value("Warehouse Unit", warehouse_unit, "default_mode_of_transport")
		or settings.get("fallback_mode_of_transport")
	)


@frappe.whitelist()
def get_movement_defaults(warehouse_unit):
	"""Defaults for the movement dialog. Public endpoint, so it checks its own permission."""
	frappe.has_permission("Warehouse Unit", "read", throw=True)
	return frappe._dict(
		mode_of_transport=_default_transport(warehouse_unit),
		movement_date=nowdate(),
	)
