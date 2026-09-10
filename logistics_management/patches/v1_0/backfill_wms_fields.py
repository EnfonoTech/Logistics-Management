"""Give the existing Receipt Notes the fields the WMS flow now needs.

qty is the important one: the CBM formula becomes length x width x height / 1e6 x qty,
so a row left at qty 0 would compute 0 CBM and every historical total -- and with it
every warehouse capacity figure derived from those totals -- would collapse.
"""

import frappe
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt

DEFAULT_CARGO_TYPE = "General"


def execute():
	backfill_package_qty()
	backfill_receipt_note()
	recompute_warehouse_derived_capacity()


def backfill_package_qty():
	"""One row meant exactly one package before qty existed."""
	if not frappe.db.has_column("Package Details", "qty"):
		return
	frappe.db.sql(
		"""UPDATE `tabPackage Details` SET qty = 1
		   WHERE parenttype = 'Receipt Note' AND (qty IS NULL OR qty = 0)"""
	)


def backfill_receipt_note():
	"""Fill company, cargo type, disposition, receipt mode, status and tracking number."""
	default_company = frappe.defaults.get_global_default("company") or frappe.db.get_value(
		"Company", {}, "name"
	)

	rows = frappe.get_all(
		"Receipt Note",
		fields=["name", "docstatus", "company", "cargo_type", "disposition", "receipt_mode",
		        "wms_status", "tracking_no", "cons_date", "creation", "warehouse_unit",
		        "job_status", "shipper", "shipper_name"],
	)

	no_company = []
	for r in rows:
		values = {}

		if not r.company:
			if default_company:
				values["company"] = default_company
			else:
				no_company.append(r.name)
		if not r.cargo_type and frappe.db.exists("Cargo Type", DEFAULT_CARGO_TYPE):
			values["cargo_type"] = DEFAULT_CARGO_TYPE
		if not r.disposition:
			# Legacy notes predate the distinction. Storage is the safe reading: it keeps
			# them out of the movement picker rather than offering history for shipment.
			values["disposition"] = "Store at Same Warehouse"
		if not r.receipt_mode:
			values["receipt_mode"] = "Delivery at Warehouse"
		if not r.cons_date:
			values["cons_date"] = frappe.utils.getdate(r.creation)
		if not r.tracking_no:
			values["tracking_no"] = make_autoname("HSM-TRK-.YYYY.-.#####")
		if r.shipper and not r.shipper_name:
			values["shipper_name"] = frappe.db.get_value("Supplier", r.shipper, "supplier_name")
		if not r.job_status:
			values["job_status"] = "Not Created"

		if r.docstatus == 1 and not r.wms_status:
			# Submitted and never moved: it is still where it was received.
			values["wms_status"] = "In Warehouse"
			values["current_warehouse_unit"] = r.warehouse_unit

		if values:
			frappe.db.set_value("Receipt Note", r.name, values, update_modified=False)

	backfill_total_packages()

	if no_company:
		frappe.log_error(
			"Receipt Notes with no company and no global default:\n" + "\n".join(no_company),
			"WMS backfill: company not set",
		)


def backfill_total_packages():
	"""total_packages is the sum of the package row quantities."""
	if not frappe.db.has_column("Receipt Note", "total_packages"):
		return
	frappe.db.sql(
		"""UPDATE `tabReceipt Note` rn
		   SET rn.total_packages = COALESCE((
		       SELECT SUM(pd.qty) FROM `tabPackage Details` pd
		       WHERE pd.parent = rn.name AND pd.parenttype = 'Receipt Note'
		   ), 0)"""
	)


def recompute_warehouse_derived_capacity():
	"""Derive occupied and utilisation from the figures already stored.

	Deliberately does NOT recompute available capacity from the receipts. Those numbers
	were partly maintained by hand and overwriting them would silently change what the
	warehouse claims to hold -- a reconciliation is a decision for HSM, not a patch.
	"""
	if not frappe.db.has_column("Warehouse Unit", "occupied_capacity_cbm"):
		return

	for unit in frappe.get_all(
		"Warehouse Unit", fields=["name", "total_area_capacity", "total_available_capacity"]
	):
		total = flt(unit.total_area_capacity)
		available = flt(unit.total_available_capacity)
		occupied = total - available
		frappe.db.set_value(
			"Warehouse Unit",
			unit.name,
			{
				"occupied_capacity_cbm": occupied,
				"utilisation_pct": (occupied / total * 100.0) if total else 0.0,
			},
			update_modified=False,
		)
