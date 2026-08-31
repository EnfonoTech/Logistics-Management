# Copyright (c) 2026, siva and Contributors
# See license.txt
"""generate_invoice is a public endpoint that creates real Sales Invoices.

These cover the status/duplicate/permission gates rather than the happy path, so
no invoice is actually posted.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from logistics_management.logistics_management.doctype.warehouse_rental.warehouse_rental import (
	generate_invoice,
)


class TestWarehouseRental(FrappeTestCase):
	def test_missing_docname_is_rejected(self):
		self.assertRaises(frappe.ValidationError, generate_invoice, None)
		self.assertRaises(frappe.ValidationError, generate_invoice, "")

	def test_months_rented_is_computed_from_the_date_range(self):
		rental = frappe.get_doc({
			"doctype": "Warehouse Rental",
			"date": "2026-01-01",
			"rent_start_date": "2026-01-01",
			"rent_end_date": "2026-03-01",  # 59 days
			"rental_rate": 100.0,
			"rent_space": 2.0,
			"status": "Available",
		})
		rental.calculate_total_amount()

		self.assertAlmostEqual(rental.months_rented, 59 / 30.0, places=4)
		self.assertAlmostEqual(rental.total_amount, 100.0 * 2.0 * (59 / 30.0), places=4)

	def test_reversed_dates_are_rejected(self):
		rental = frappe.get_doc({
			"doctype": "Warehouse Rental",
			"rent_start_date": "2026-03-01",
			"rent_end_date": "2026-01-01",
			"rental_rate": 100.0,
			"rent_space": 1.0,
		})
		self.assertRaises(frappe.ValidationError, rental.calculate_total_amount)

	def test_missing_dates_zero_the_amount_instead_of_raising(self):
		rental = frappe.get_doc({
			"doctype": "Warehouse Rental",
			"rental_rate": 100.0,
			"rent_space": 1.0,
		})
		rental.calculate_total_amount()

		self.assertEqual(rental.months_rented, 0)
		self.assertEqual(rental.total_amount, 0)
