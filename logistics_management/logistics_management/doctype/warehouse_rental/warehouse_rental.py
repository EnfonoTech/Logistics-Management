# Copyright (c) 2024, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, date_diff, flt, today

# Rental rates are quoted per month; a month is billed as 30 days.
DAYS_PER_BILLED_MONTH = 30.0


class WarehouseRental(Document):
	def validate(self):
		self.calculate_total_amount()

	def calculate_total_amount(self):
		if not (self.rent_start_date and self.rent_end_date):
			self.months_rented = 0
			self.total_amount = 0
			return

		days = date_diff(self.rent_end_date, self.rent_start_date)
		if days < 0:
			frappe.throw(_("Rent End Date cannot be before Rent Start Date."))

		self.months_rented = flt(days) / DAYS_PER_BILLED_MONTH
		self.total_amount = flt(self.rental_rate) * flt(self.rent_space) * flt(self.months_rented)


@frappe.whitelist()
def generate_invoice(docname):
	"""Raise the Sales Invoice for an occupied Warehouse Rental.

	This is a public HTTP endpoint. It creates a real Sales Invoice, so it checks
	permissions explicitly rather than relying on whoever can reach the button.
	"""
	if not docname:
		frappe.throw(_("Document name is required to generate the invoice."))

	frappe.has_permission("Warehouse Rental", "write", doc=docname, throw=True)
	frappe.has_permission("Sales Invoice", "create", throw=True)

	doc = frappe.get_doc("Warehouse Rental", docname)

	if doc.status != "Occupied":
		frappe.throw(_("Invoice generation is only allowed for 'Occupied' status."))

	if doc.invoice_number:
		frappe.throw(
			_("Sales Invoice {0} already exists for this Warehouse Rental.").format(doc.invoice_number)
		)

	if not doc.customer:
		frappe.throw(_("Customer is required to generate the invoice."))
	if not doc.warehouse_space_item:
		frappe.throw(_("Warehouse Space Item is required to generate the invoice."))

	doc.calculate_total_amount()

	# This site runs three companies, so the invoice must say which one explicitly
	# rather than falling back to a global default.
	company = doc.company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Company is required to generate the invoice."))

	invoice = frappe.get_doc({
		"doctype": "Sales Invoice",
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"customer": doc.customer,
		"custom_job_number": doc.job_details,
		"posting_date": today(),
		"due_date": add_days(today(), 30),
		"items": [{
			"item_code": doc.warehouse_space_item,
			"qty": 1,
			"rate": flt(doc.total_amount),
		}],
	})
	invoice.insert()

	doc.db_set("invoice_number", invoice.name)

	frappe.msgprint(
		_("Sales Invoice {0} generated successfully.").format(
			frappe.utils.get_link_to_form("Sales Invoice", invoice.name)
		),
		indicator="green",
		alert=True,
	)
	return invoice.name
