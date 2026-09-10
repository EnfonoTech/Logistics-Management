"""Storage rate lookup, keyed on customer and cargo type.

The rate is per CBM per day. It is never flat: HSM negotiate it per customer, and it
varies again by cargo class -- general, dangerous, liquid chemical, reefer.

Two entry points on purpose. find_storage_rate() returns None so a monthly accrual can
report the gap and carry on; get_storage_rate() throws so nothing prices storage at
zero by accident. In warehouse_3pl, create_billing_transaction() returned early when
rate and minimum were both zero, so a missing rate produced no billing row at all and
the work stayed billable forever while looking finished.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def find_storage_rate(customer, cargo_type, on_date=None):
	"""The Warehouse Storage Rate in force for this customer and cargo type, or None."""
	if not customer or not cargo_type:
		return None

	on_date = getdate(on_date or nowdate())

	rate = frappe.db.get_value(
		"Warehouse Storage Rate",
		{
			"customer": customer,
			"cargo_type": cargo_type,
			"disabled": 0,
			"valid_from": ["<=", on_date],
		},
		["name", "rate_per_cbm_per_day", "minimum_charge", "valid_from", "valid_to"],
		order_by="valid_from desc",
		as_dict=True,
	)

	if not rate:
		return None
	if rate.valid_to and getdate(rate.valid_to) < on_date:
		return None
	if flt(rate.rate_per_cbm_per_day) <= 0:
		# A zero rate is a configuration mistake, not a free customer. Treat it as absent
		# so the caller reports it rather than billing nothing.
		return None

	return rate


def get_storage_rate(customer, cargo_type, on_date=None):
	"""Same lookup, but throws when no usable rate applies. Use this before billing."""
	rate = find_storage_rate(customer, cargo_type, on_date=on_date)
	if rate:
		return rate

	frappe.throw(
		_("No usable storage rate for customer {0} with cargo type {1} on {2}."
		  " Create a Warehouse Storage Rate with a non-zero rate before billing this storage.")
		.format(
			frappe.bold(customer or _("(not set)")),
			frappe.bold(cargo_type or _("(not set)")),
			frappe.format(getdate(on_date or nowdate()), "Date"),
		),
		title=_("Storage Rate Missing"),
	)


def calculate_storage_charge(cbm, days, rate_per_cbm_per_day, minimum_charge=0.0):
	"""cbm x days x rate, floored at the minimum charge if one is set."""
	amount = flt(cbm) * flt(days) * flt(rate_per_cbm_per_day)
	minimum_charge = flt(minimum_charge)
	return max(amount, minimum_charge) if minimum_charge else amount
