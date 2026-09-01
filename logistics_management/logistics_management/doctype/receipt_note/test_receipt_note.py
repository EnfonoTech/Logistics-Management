# Copyright (c) 2026, siva and Contributors
# See license.txt
"""Warehouse capacity round-trip.

Capacity is a stored counter mutated from two directions, so the invariant that
matters is that it comes back to where it started once a Receipt Note is
cancelled. Before on_cancel existed, cancelling silently lost the space.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

UNIT = "_Test Capacity Unit"
STARTING_CAPACITY = 500.0


class TestReceiptNote(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("Warehouse Unit", UNIT):
			frappe.get_doc({
				"doctype": "Warehouse Unit",
				"warehouse_name": UNIT,
				"total_area_capacity": STARTING_CAPACITY,
				"total_available_capacity": STARTING_CAPACITY,
			}).insert()
		else:
			frappe.db.set_value("Warehouse Unit", UNIT, "total_available_capacity", STARTING_CAPACITY)

	def _capacity(self):
		return flt(frappe.db.get_value("Warehouse Unit", UNIT, "total_available_capacity"))

	def _note(self, waybill, cbm):
		return frappe.get_doc({
			"doctype": "Receipt Note",
			"waybill_no": waybill,
			"warehouse_unit": UNIT,
			"cons_date": frappe.utils.today(),
			"package_details": [{"cbm": cbm}],
			"total_cbm": cbm,
		}).insert()

	def test_submit_consumes_capacity_and_cancel_gives_it_back(self):
		note = self._note("_TEST-RN-ROUNDTRIP", 120.0)

		note.submit()
		self.assertEqual(self._capacity(), STARTING_CAPACITY - 120.0)

		note.cancel()
		self.assertEqual(self._capacity(), STARTING_CAPACITY)

	def test_submit_is_refused_when_capacity_would_go_negative(self):
		note = self._note("_TEST-RN-OVERFLOW", STARTING_CAPACITY + 1)

		self.assertRaises(frappe.ValidationError, note.submit)
		self.assertEqual(self._capacity(), STARTING_CAPACITY)

	def test_null_cbm_rows_do_not_raise(self):
		"""Raw attribute arithmetic used to blow up mid-submit on an empty CBM."""
		note = frappe.get_doc({
			"doctype": "Receipt Note",
			"waybill_no": "_TEST-RN-NULLCBM",
			"warehouse_unit": UNIT,
			"cons_date": frappe.utils.today(),
			"package_details": [{"cbm": None}, {"cbm": 10.0}],
		}).insert()

		note.submit()
		self.assertEqual(self._capacity(), STARTING_CAPACITY - 10.0)

	def test_note_without_a_warehouse_unit_is_a_no_op(self):
		before = self._capacity()
		note = frappe.get_doc({
			"doctype": "Receipt Note",
			"waybill_no": "_TEST-RN-NOUNIT",
			"cons_date": frappe.utils.today(),
			"package_details": [{"cbm": 25.0}],
		}).insert()

		note.submit()
		self.assertEqual(self._capacity(), before)
