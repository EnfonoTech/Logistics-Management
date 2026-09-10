# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class WarehouseStorageRate(Document):
	"""One customer's agreed storage rate for one cargo class, per CBM per day."""

	def validate(self):
		self.set_default_currency()
		self.validate_rate()
		self.validate_validity_window()
		self.validate_no_overlap()

	def set_default_currency(self):
		if self.currency:
			return
		company = frappe.defaults.get_user_default("Company")
		self.currency = (
			frappe.db.get_value("Company", company, "default_currency") if company else None
		) or frappe.db.get_single_value("Global Defaults", "default_currency")

	def validate_rate(self):
		if flt(self.rate_per_cbm_per_day) <= 0:
			frappe.throw(
				_("Rate per CBM per day must be greater than zero. A zero rate bills nothing"
				  " at all -- tick Disabled instead if this customer is not to be charged."),
				title=_("Rate Cannot Be Zero"),
			)
		if flt(self.minimum_charge) < 0:
			frappe.throw(_("Minimum charge cannot be negative."))

	def validate_validity_window(self):
		if self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
			frappe.throw(
				_("Valid To {0} is before Valid From {1}.").format(self.valid_to, self.valid_from)
			)

	def validate_no_overlap(self):
		"""Two live rates for the same customer and cargo type would make billing ambiguous."""
		if self.disabled:
			return

		siblings = frappe.get_all(
			"Warehouse Storage Rate",
			filters={
				"customer": self.customer,
				"cargo_type": self.cargo_type,
				"disabled": 0,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "valid_from", "valid_to"],
		)

		start = getdate(self.valid_from)
		end = getdate(self.valid_to) if self.valid_to else None

		for other in siblings:
			other_start = getdate(other.valid_from)
			other_end = getdate(other.valid_to) if other.valid_to else None

			# Two windows overlap unless one ends before the other begins.
			if (end and end < other_start) or (other_end and other_end < start):
				continue

			frappe.throw(
				_("Storage rate {0} already covers {1} / {2} from {3}{4}."
				  " Close it off with a Valid To date, or disable it, before adding another.")
				.format(
					frappe.bold(other.name), self.customer, self.cargo_type,
					frappe.format(other_start, "Date"),
					_(" to {0}").format(frappe.format(other_end, "Date")) if other_end else "",
				),
				title=_("Overlapping Storage Rate"),
			)
