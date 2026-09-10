# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CargoType(Document):
	"""Cargo class. It is what makes the storage rate vary, alongside the customer.

	HSM: "dangerous cargo, liquid chemicals, general, and items for cooling -- so the
	rate will never be fixed, each one has its own rate."
	"""

	pass
