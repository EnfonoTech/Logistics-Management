# Copyright (c) 2026, Enfono Technologies and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from logistics_management.wms import testing
from logistics_management.wms.rates import (
	calculate_storage_charge,
	find_storage_rate,
	get_storage_rate,
)


class TestWarehouseStorageRate(FrappeTestCase):
	def setUp(self):
		self.customer = testing.customer("Rate")
		testing.cargo_type("General")
		testing.cargo_type("Dangerous Cargo")
		frappe.db.delete("Warehouse Storage Rate", {"customer": self.customer})

	def _rate(self, cargo="General", rate=3.0, valid_from="2026-01-01", valid_to=None,
	          minimum=0.0, disabled=0):
		return frappe.get_doc({
			"doctype": "Warehouse Storage Rate",
			"customer": self.customer,
			"cargo_type": cargo,
			"rate_per_cbm_per_day": rate,
			"minimum_charge": minimum,
			"valid_from": valid_from,
			"valid_to": valid_to,
			"disabled": disabled,
		}).insert(ignore_permissions=True)

	# ── validation ────────────────────────────────────────────────────────────────

	def test_zero_rate_is_refused(self):
		"""A zero rate bills nothing at all, which is how 3PL storage went unbilled."""
		doc = frappe.get_doc({
			"doctype": "Warehouse Storage Rate",
			"customer": self.customer,
			"cargo_type": "General",
			"rate_per_cbm_per_day": 0,
			"valid_from": "2026-01-01",
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_valid_to_before_valid_from_is_refused(self):
		doc = frappe.get_doc({
			"doctype": "Warehouse Storage Rate",
			"customer": self.customer,
			"cargo_type": "General",
			"rate_per_cbm_per_day": 3,
			"valid_from": "2026-06-01",
			"valid_to": "2026-01-01",
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_overlapping_live_rates_are_refused(self):
		"""Two live rates for one customer and cargo class make billing ambiguous."""
		self._rate(valid_from="2026-01-01")
		with self.assertRaises(frappe.ValidationError):
			self._rate(valid_from="2026-03-01", rate=4.5)

	def test_a_closed_off_rate_allows_its_successor(self):
		""""Once the rate is fixed it continues like that" -- until renegotiated."""
		self._rate(valid_from="2026-01-01", valid_to="2026-05-31", rate=3.0)
		successor = self._rate(valid_from="2026-06-01", rate=4.5)
		self.assertEqual(successor.rate_per_cbm_per_day, 4.5)

	def test_different_cargo_types_do_not_collide(self):
		"""The rate varies by cargo class as well as by customer."""
		self._rate(cargo="General", rate=3.0)
		hazardous = self._rate(cargo="Dangerous Cargo", rate=6.0)
		self.assertEqual(hazardous.rate_per_cbm_per_day, 6.0)

	# ── lookup ────────────────────────────────────────────────────────────────────

	def test_lookup_picks_the_rate_in_force_on_the_date(self):
		self._rate(valid_from="2026-01-01", valid_to="2026-05-31", rate=3.0)
		self._rate(valid_from="2026-06-01", rate=4.5)

		self.assertEqual(
			find_storage_rate(self.customer, "General", "2026-03-15").rate_per_cbm_per_day, 3.0
		)
		self.assertEqual(
			find_storage_rate(self.customer, "General", "2026-08-15").rate_per_cbm_per_day, 4.5
		)

	def test_lookup_returns_none_before_the_rate_starts(self):
		self._rate(valid_from="2026-06-01")
		self.assertIsNone(find_storage_rate(self.customer, "General", "2026-01-01"))

	def test_lookup_ignores_a_disabled_rate(self):
		self._rate(disabled=1)
		self.assertIsNone(find_storage_rate(self.customer, "General", "2026-03-01"))

	def test_get_storage_rate_throws_when_absent(self):
		"""find_ returns None so a month's accrual can carry on; get_ throws so nothing
		prices storage at zero by accident."""
		self.assertRaises(
			frappe.ValidationError, get_storage_rate, self.customer, "General", "2026-03-01"
		)

	# ── arithmetic ────────────────────────────────────────────────────────────────

	def test_charge_is_cbm_times_days_times_rate(self):
		"""19 CBM for 12 days at QAR 3.00 per CBM per day is QAR 684.00."""
		self.assertAlmostEqual(calculate_storage_charge(19, 12, 3.0), 684.0, places=2)

	def test_dangerous_cargo_at_double_the_rate_doubles_the_charge(self):
		self.assertAlmostEqual(calculate_storage_charge(19, 12, 6.0), 1368.0, places=2)

	def test_minimum_charge_is_a_floor_not_an_addition(self):
		self.assertAlmostEqual(calculate_storage_charge(1, 1, 3.0, minimum_charge=50.0), 50.0,
		                       places=2)
		self.assertAlmostEqual(calculate_storage_charge(19, 12, 3.0, minimum_charge=50.0), 684.0,
		                       places=2)
