"""Storage accrual and invoicing: CBM x days x the customer's rate for that cargo class.

Split deliberately in two. Accrual is arithmetic, so a scheduler may run it. Invoicing
creates money documents, so it stays a human action -- HSM invoice monthly and want to
look at the figures first.

Day counting is INCLUSIVE of both the receipt day and the last stored day, which is the
usual commercial convention; it is stated on every Storage Charge so HSM can check it.
"""

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from logistics_management.wms.rates import calculate_storage_charge, find_storage_rate

STORAGE_ITEM_CODE = "WMS-STORAGE"
STORED_DISPOSITION = "Store at Same Warehouse"


def chargeable_days(entry_date, exit_date, period_start, period_end):
	"""Inclusive day count for the part of a stay that falls inside the period."""
	entry_date, period_start, period_end = getdate(entry_date), getdate(period_start), getdate(period_end)
	window_start = max(entry_date, period_start)
	window_end = min(getdate(exit_date), period_end) if exit_date else period_end

	if window_end < window_start:
		return 0, None, None
	return (window_end - window_start).days + 1, window_start, window_end


@frappe.whitelist()
def generate_storage_charges(period_start=None, period_end=None, company=None, customer=None):
	"""Accrue storage for every consignment stored during the period.

	Idempotent: a Storage Charge already invoiced is never touched, and an uninvoiced one
	for the same receipt and period is recomputed in place rather than duplicated.
	"""
	frappe.has_permission("Storage Charge", "create", throw=True)

	if not period_start or not period_end:
		last_month = add_months(getdate(nowdate()), -1)
		period_start = get_first_day(last_month)
		period_end = get_last_day(last_month)
	period_start, period_end = getdate(period_start), getdate(period_end)

	if period_end < period_start:
		frappe.throw(_("Period end {0} is before period start {1}.").format(period_end, period_start))

	filters = {"docstatus": 1, "disposition": STORED_DISPOSITION}
	if company:
		filters["company"] = company
	if customer:
		filters["consignee"] = customer

	receipts = frappe.get_all(
		"Receipt Note",
		filters=filters,
		fields=["name", "consignee", "cargo_type", "warehouse_unit", "company", "total_cbm",
		        "cons_date", "creation", "wms_delivery_date", "wms_status"],
	)

	created, updated, skipped = [], [], []

	for r in receipts:
		entry_date = r.cons_date or getdate(r.creation)
		days, window_start, window_end = chargeable_days(
			entry_date, r.wms_delivery_date, period_start, period_end
		)
		if not days or flt(r.total_cbm) <= 0:
			continue

		if not r.cargo_type:
			skipped.append((r.name, _("no cargo type set")))
			continue

		existing = frappe.db.get_value(
			"Storage Charge",
			{"receipt_note": r.name, "period_start": period_start, "period_end": period_end},
			["name", "invoiced"],
			as_dict=True,
		)
		if existing and cint(existing.invoiced):
			continue

		# A missing rate must be visible, not silently priced at zero -- but one customer
		# without a rate must not abort the whole month's accrual for everyone else.
		rate = find_storage_rate(r.consignee, r.cargo_type, on_date=window_start)
		if not rate:
			skipped.append((r.name, _("no usable storage rate for {0} / {1}").format(
				r.consignee, r.cargo_type)))
			continue

		amount = calculate_storage_charge(
			r.total_cbm, days, rate.rate_per_cbm_per_day, rate.minimum_charge
		)

		values = {
			"receipt_note": r.name,
			"customer": r.consignee,
			"cargo_type": r.cargo_type,
			"warehouse_unit": r.warehouse_unit,
			"company": r.company,
			"period_start": period_start,
			"period_end": period_end,
			"stored_from": window_start,
			"stored_to": window_end,
			"days": days,
			"cbm": flt(r.total_cbm),
			"storage_rate": rate.name,
			"rate_per_cbm_per_day": flt(rate.rate_per_cbm_per_day),
			"minimum_charge": flt(rate.minimum_charge),
			"amount": amount,
		}

		if existing:
			charge = frappe.get_doc("Storage Charge", existing.name)
			charge.update(values)
			charge.save()
			updated.append(charge.name)
		else:
			charge = frappe.new_doc("Storage Charge")
			charge.update(values)
			charge.insert()
			created.append(charge.name)

	return frappe._dict(
		period_start=period_start, period_end=period_end,
		created=created, updated=updated, skipped=skipped,
	)


@frappe.whitelist()
def create_storage_invoices(period_start, period_end, company):
	"""One draft Sales Invoice per customer for the period's uninvoiced storage.

	Left in draft on purpose. The charges are stamped as invoiced by the Sales Invoice's
	own submit hook, so a cancelled invoice releases them again -- the traceability that
	warehouse_3pl's Billing Transaction never had.
	"""
	frappe.has_permission("Sales Invoice", "create", throw=True)
	period_start, period_end = getdate(period_start), getdate(period_end)

	charges = frappe.get_all(
		"Storage Charge",
		filters={
			"period_start": period_start,
			"period_end": period_end,
			"company": company,
			"invoiced": 0,
			"sales_invoice": ["in", [None, ""]],
		},
		fields=["name", "customer", "receipt_note", "cbm", "days", "rate_per_cbm_per_day",
		        "minimum_charge", "amount", "cargo_type", "warehouse_unit"],
		order_by="customer, receipt_note",
	)
	if not charges:
		frappe.throw(_("No uninvoiced storage charges for {0} between {1} and {2}.").format(
			company, period_start, period_end))

	_ensure_storage_item()

	by_customer = {}
	for c in charges:
		by_customer.setdefault(c.customer, []).append(c)

	invoices = []
	for customer, rows in by_customer.items():
		si = frappe.new_doc("Sales Invoice")
		si.customer = customer
		si.company = company
		si.posting_date = period_end
		si.set_posting_time = 1
		si.update_stock = 0

		for c in rows:
			description = _(
				"Storage {0} to {1}: {2} CBM for {3} day(s) at {4} per CBM per day"
				" ({5}, waybill {6})"
			).format(
				frappe.format(period_start, "Date"), frappe.format(period_end, "Date"),
				flt(c.cbm), cint(c.days),
				frappe.format_value(c.rate_per_cbm_per_day, {"fieldtype": "Currency"}),
				c.cargo_type, c.receipt_note,
			)
			# qty x rate reproduces the amount exactly in CBM-days, unless a minimum
			# charge kicked in -- then a single line for the minimum is the honest shape.
			cbm_days = flt(c.cbm) * cint(c.days)
			exact = cbm_days and abs(cbm_days * flt(c.rate_per_cbm_per_day) - flt(c.amount)) < 0.005

			si.append("items", {
				"item_code": STORAGE_ITEM_CODE,
				"qty": cbm_days if exact else 1,
				"rate": flt(c.rate_per_cbm_per_day) if exact else flt(c.amount),
				"description": description,
				"wms_storage_charge": c.name,
			})

		si.set_missing_values()
		if not si.due_date:
			# set_missing_values only fills due_date when payment terms resolve; without
			# it the desk refuses the invoice. This is the #5 fix from the 3PL work.
			si.due_date = si.posting_date
		si.insert()
		invoices.append(si.name)

		for c in rows:
			frappe.db.set_value("Storage Charge", c.name, "sales_invoice", si.name,
			                    update_modified=False)

	return invoices


def _ensure_storage_item():
	"""The service item the storage line is billed on.

	This is HSM's own service, not customer cargo -- it is not a stock item and it never
	touches the Stock Ledger. Without an item_code ERPNext refuses the invoice with
	"Income Account None does not belong to Company X", the same failure that broke the
	3PL invoices.
	"""
	if frappe.db.exists("Item", STORAGE_ITEM_CODE):
		return STORAGE_ITEM_CODE

	item_group = "Services" if frappe.db.exists("Item Group", "Services") else \
		frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")

	item = frappe.new_doc("Item")
	item.item_code = STORAGE_ITEM_CODE
	item.item_name = "Warehouse Storage"
	item.description = "Warehouse storage billed per CBM per day"
	item.item_group = item_group
	item.stock_uom = uom
	item.is_stock_item = 0
	item.is_sales_item = 1
	item.is_purchase_item = 0
	item.include_item_in_manufacturing = 0
	item.insert(ignore_permissions=True)
	return item.name


def stamp_charges_on_invoice_submit(doc, method=None):
	"""Mark storage charges invoiced when their Sales Invoice is submitted."""
	_set_invoiced_flag(doc, 1)


def release_charges_on_invoice_cancel(doc, method=None):
	"""Release storage charges when their Sales Invoice is cancelled, so they re-bill."""
	_set_invoiced_flag(doc, 0)


def _set_invoiced_flag(doc, invoiced):
	names = {row.get("wms_storage_charge") for row in (doc.get("items") or [])
	         if row.get("wms_storage_charge")}
	names |= set(frappe.get_all(
		"Storage Charge", filters={"sales_invoice": doc.name}, pluck="name"
	))
	for name in names:
		if frappe.db.exists("Storage Charge", name):
			frappe.db.set_value(
				"Storage Charge", name,
				{"invoiced": cint(invoiced), "sales_invoice": doc.name if invoiced else None},
				update_modified=False,
			)


def accrue_last_month():
	"""Monthly scheduler entry. Accrues only -- it never creates an invoice."""
	try:
		result = generate_storage_charges()
		if result.skipped:
			frappe.log_error(
				frappe.as_json(result.skipped, indent=2),
				"WMS storage accrual: consignments skipped",
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WMS storage accrual failed")
