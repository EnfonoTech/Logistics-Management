# Copyright (c) 2026, Enfono Technologies and contributors
# See license.txt

"""The settings decide what customers are charged, so they get their own tests."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from logistics_management.wms import capacity, settings, storage_billing, testing

SETTINGS = "Warehouse Management Settings"


def set_setting(**kwargs):
	for k, v in kwargs.items():
		frappe.db.set_single_value(SETTINGS, k, v)
	frappe.clear_cache(doctype=SETTINGS)


class TestWarehouseManagementSettings(FrappeTestCase):
	def setUp(self):
		self.customer = testing.customer("Settings")
		self.wh = testing.warehouse("Settings", capacity_cbm=100.0)
		testing.cargo_type("General")
		# Every test starts from the shipped defaults.
		set_setting(
			dimension_uom="Centimetre",
			day_count_method="Both days inclusive",
			minimum_chargeable_days=0,
			capacity_enforcement="Block the receipt",
			treat_zero_capacity_as_unlimited=1,
		)

	# ── dimensions ────────────────────────────────────────────────────────────────

	def test_dimension_unit_changes_the_cbm(self):
		"""The divisor used to be a module constant assuming centimetres."""
		set_setting(dimension_uom="Centimetre")
		cm = testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 1),), submit=False)
		self.assertAlmostEqual(flt(cm.total_cbm), 1.0, places=6)

		set_setting(dimension_uom="Millimetre")
		mm = testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 1),), submit=False)
		self.assertAlmostEqual(flt(mm.total_cbm), 0.001, places=9)

		set_setting(dimension_uom="Metre")
		m = testing.receipt(self.customer, self.wh, packages=((1, 1, 1, 1),), submit=False)
		self.assertAlmostEqual(flt(m.total_cbm), 1.0, places=6)

	def test_inch_divisor_is_right(self):
		set_setting(dimension_uom="Inch")
		# A 12in cube is 1 cubic foot = 0.0283168 m3
		doc = testing.receipt(self.customer, self.wh, packages=((12, 12, 12, 1),), submit=False)
		self.assertAlmostEqual(flt(doc.total_cbm), 0.0283168, places=6)

	# ── day counting ──────────────────────────────────────────────────────────────

	# 1st to 12th: 12 days inclusive, 11 charging only the day in, 10 excluding both.
	def test_day_count_method_changes_the_bill(self):
		set_setting(day_count_method="Both days inclusive")
		self.assertEqual(storage_billing.chargeable_days(
			"2026-08-01", "2026-08-12", "2026-08-01", "2026-08-31")[0], 12)

		set_setting(day_count_method="Charge the day in, not the day out")
		self.assertEqual(storage_billing.chargeable_days(
			"2026-08-01", "2026-08-12", "2026-08-01", "2026-08-31")[0], 11)

		set_setting(day_count_method="Exclude both days")
		self.assertEqual(storage_billing.chargeable_days(
			"2026-08-01", "2026-08-12", "2026-08-01", "2026-08-31")[0], 10)

	def test_minimum_chargeable_days_is_a_floor(self):
		set_setting(day_count_method="Both days inclusive", minimum_chargeable_days=7)
		# A two-day stay bills as seven.
		self.assertEqual(storage_billing.chargeable_days(
			"2026-08-01", "2026-08-02", "2026-08-01", "2026-08-31")[0], 7)
		# A long stay is untouched.
		self.assertEqual(storage_billing.chargeable_days(
			"2026-08-01", "2026-08-20", "2026-08-01", "2026-08-31")[0], 20)

	def test_minimum_does_not_invent_days_for_a_stay_outside_the_period(self):
		set_setting(minimum_chargeable_days=7)
		self.assertEqual(storage_billing.chargeable_days(
			"2026-06-01", "2026-06-30", "2026-08-01", "2026-08-31")[0], 0)

	# ── capacity enforcement ──────────────────────────────────────────────────────

	def test_block_refuses_an_overflowing_receipt(self):
		set_setting(capacity_enforcement="Block the receipt")
		small = testing.warehouse("SettingsTiny", capacity_cbm=5.0)
		doc = testing.receipt(self.customer, small, packages=((100, 100, 100, 50),), submit=False)
		self.assertRaises(frappe.ValidationError, doc.submit)

	def test_warn_only_lets_it_through(self):
		set_setting(capacity_enforcement="Warn only")
		small = testing.warehouse("SettingsTiny", capacity_cbm=5.0)
		doc = testing.receipt(self.customer, small, packages=((100, 100, 100, 50),), submit=False)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		# The overflow is recorded honestly rather than hidden.
		self.assertLess(testing.available(small), 0)

	def test_zero_capacity_warehouse_accepts_goods(self):
		"""GUANJZHOU and YIWU on hsm-erp are set to 0 and refused every single receipt."""
		unset = testing.warehouse("SettingsUnset", capacity_cbm=0.0)
		set_setting(treat_zero_capacity_as_unlimited=1)
		doc = testing.receipt(self.customer, unset, packages=((100, 100, 100, 9),), submit=False)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_zero_capacity_can_still_be_enforced_if_wanted(self):
		unset = testing.warehouse("SettingsUnset", capacity_cbm=0.0)
		set_setting(treat_zero_capacity_as_unlimited=0, capacity_enforcement="Block the receipt")
		doc = testing.receipt(self.customer, unset, packages=((100, 100, 100, 9),), submit=False)
		self.assertRaises(frappe.ValidationError, doc.submit)

	def test_do_not_check_skips_enforcement_entirely(self):
		set_setting(capacity_enforcement="Do not check")
		small = testing.warehouse("SettingsTiny", capacity_cbm=5.0)
		doc = testing.receipt(self.customer, small, packages=((100, 100, 100, 50),), submit=False)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	# ── validation on the settings themselves ─────────────────────────────────────

	def test_a_whole_number_storage_uom_is_refused(self):
		"""A whole-number UOM makes every storage invoice fail with a fractional qty."""
		if not frappe.db.exists("UOM", "Nos"):
			self.skipTest("no Nos UOM on this site")
		frappe.db.set_value("UOM", "Nos", "must_be_whole_number", 1)
		doc = frappe.get_single(SETTINGS)
		doc.storage_uom = "Nos"
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()

	def test_a_series_with_no_placeholder_is_refused(self):
		doc = frappe.get_single(SETTINGS)
		doc.tracking_number_series = "HSM-TRK-FIXED"
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()

	def test_accrual_day_must_exist_in_every_month(self):
		doc = frappe.get_single(SETTINGS)
		doc.accrual_day_of_month = 31
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()

	# ── fallbacks ─────────────────────────────────────────────────────────────────

	def test_accessors_fall_back_to_the_old_hardcoded_values(self):
		"""A site whose Single has never been saved must behave as it did before."""
		self.assertEqual(settings.DEFAULTS["dimension_uom"], "Centimetre")
		self.assertEqual(settings.DAY_COUNT_OFFSETS["Both days inclusive"], 1)
		self.assertAlmostEqual(settings.DIMENSION_DIVISORS["Centimetre"], 1_000_000.0)
