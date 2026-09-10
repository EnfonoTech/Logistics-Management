"""Fixture helpers shared by the WMS tests.

Deliberately not named test_* so the runner does not try to execute it as a suite.
Everything here is idempotent: the suite is run repeatedly against the same site.
"""

import frappe
from frappe.utils import flt, nowdate

PREFIX = "_WMS Test"


def company():
	"""An existing Company. Creating one pulls in the whole chart of accounts, which is
	far too heavy for a unit test, so the site's default is reused."""
	name = frappe.defaults.get_global_default("company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not name:
		raise frappe.ValidationError("No Company on this site; WMS tests need one.")
	return name


def customer(suffix="A"):
	name = f"{PREFIX} Customer {suffix}"
	if not frappe.db.exists("Customer", name):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Company",
		}).insert(ignore_permissions=True)
	return name


def cargo_type(name="General"):
	if not frappe.db.exists("Cargo Type", name):
		frappe.get_doc({"doctype": "Cargo Type", "cargo_type": name}).insert(
			ignore_permissions=True
		)
	return name


def pallet_type(name="CTN"):
	if not frappe.db.exists("Pallet Types", name):
		frappe.get_doc({"doctype": "Pallet Types", "types": name}).insert(ignore_permissions=True)
	return name


def warehouse(suffix="Origin", capacity_cbm=1000.0):
	"""A Warehouse Unit reset to full capacity, so each test starts from a known figure."""
	name = f"{PREFIX} WH {suffix}"
	if not frappe.db.exists("Warehouse Unit", name):
		frappe.get_doc({
			"doctype": "Warehouse Unit",
			"warehouse_name": name,
			"total_area_capacity": capacity_cbm,
			"total_available_capacity": capacity_cbm,
		}).insert(ignore_permissions=True)

	frappe.db.set_value(
		"Warehouse Unit",
		name,
		{
			"total_area_capacity": capacity_cbm,
			"total_available_capacity": capacity_cbm,
			"occupied_capacity_cbm": 0,
			"utilisation_pct": 0,
		},
		update_modified=False,
	)
	return name


def storage_rate(cust, cargo="General", rate=3.0, minimum=0.0, valid_from="2020-01-01"):
	existing = frappe.db.get_value(
		"Warehouse Storage Rate", {"customer": cust, "cargo_type": cargo, "disabled": 0}, "name"
	)
	if existing:
		frappe.db.set_value("Warehouse Storage Rate", existing, {
			"rate_per_cbm_per_day": rate, "minimum_charge": minimum,
		}, update_modified=False)
		return existing

	doc = frappe.get_doc({
		"doctype": "Warehouse Storage Rate",
		"customer": cust,
		"cargo_type": cargo_type(cargo),
		"rate_per_cbm_per_day": rate,
		"minimum_charge": minimum,
		"valid_from": valid_from,
	}).insert(ignore_permissions=True)
	return doc.name


def receipt(
	cust,
	wh,
	packages=((40, 30, 30, 10),),
	disposition="Move to Other Warehouse",
	submit=True,
	waybill_no=None,
	cons_date=None,
	cargo="General",
):
	"""A Receipt Note. `packages` rows are (length, width, height, qty) in cm."""
	doc = frappe.new_doc("Receipt Note")
	doc.waybill_no = waybill_no or frappe.generate_hash(length=10).upper()
	doc.cons_date = cons_date or nowdate()
	doc.company = company()
	doc.warehouse_unit = wh
	doc.cargo_type = cargo_type(cargo)
	doc.consignee = cust
	doc.receipt_mode = "Delivery at Warehouse"
	doc.disposition = disposition

	for length, width, height, qty in packages:
		doc.append("package_details", {
			"type": pallet_type(),
			"description": "Test cargo",
			"qty": qty,
			"length": length,
			"width": width,
			"height": height,
		})

	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def available(wh):
	return flt(frappe.db.get_value("Warehouse Unit", wh, "total_available_capacity"))
