# Copyright (c) 2026, siva and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from logistics_management.wms import capacity, testing


class TestReceiptNote(FrappeTestCase):
	def setUp(self):
		self.customer = testing.customer("A")
		self.wh = testing.warehouse("Origin", capacity_cbm=100.0)

	# ── CBM arithmetic ────────────────────────────────────────────────────────────

	def test_row_cbm_multiplies_by_qty(self):
		"""10 cartons at 40x30x30 cm are 0.36 CBM, not 0.036.

		This is the whole point of adding qty: before it, one row meant one package and
		ten cartons were billed and stored as one.
		"""
		doc = testing.receipt(self.customer, self.wh, packages=((40, 30, 30, 10),), submit=False)
		self.assertAlmostEqual(flt(doc.package_details[0].cbm), 0.36, places=6)
		self.assertAlmostEqual(flt(doc.total_cbm), 0.36, places=6)
		self.assertEqual(doc.total_packages, 10)

	def test_total_cbm_sums_mixed_rows(self):
		doc = testing.receipt(
			self.customer, self.wh,
			packages=((40, 30, 30, 10), (120, 100, 150, 2)),
			submit=False,
		)
		# 0.036 x 10 = 0.36 ; 1.8 x 2 = 3.6
		self.assertAlmostEqual(flt(doc.package_details[0].cbm), 0.36, places=6)
		self.assertAlmostEqual(flt(doc.package_details[1].cbm), 3.6, places=6)
		self.assertAlmostEqual(flt(doc.total_cbm), 3.96, places=6)
		self.assertEqual(doc.total_packages, 12)

	def test_missing_qty_counts_as_one_package(self):
		"""The migration reading: a row without a quantity is a single package.

		If this ever returned 0 CBM, every historical total and every warehouse capacity
		figure derived from them would collapse to zero.
		"""
		doc = testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 1),), submit=False)
		doc.package_details[0].qty = 0
		doc.save()
		self.assertEqual(doc.package_details[0].qty, 1)
		self.assertAlmostEqual(flt(doc.total_cbm), 1.0, places=6)

	def test_a_blank_grid_row_is_not_a_package(self):
		"""A leftover empty row put "Total No. of Package(s): 3" on a note carrying two."""
		doc = testing.receipt(
			self.customer, self.wh, packages=((80, 46, 43, 1), (75, 43, 42, 1)), submit=False
		)
		doc.append("package_details", {"qty": 1})      # the blank row the grid leaves behind
		doc.save()
		self.assertEqual(doc.total_packages, 2)
		self.assertAlmostEqual(flt(doc.package_details[2].cbm), 0.0, places=6)

	def test_a_blank_row_with_a_real_quantity_still_counts(self):
		"""Somebody typing 5 meant it, even with no type or size yet."""
		doc = testing.receipt(self.customer, self.wh, packages=((80, 46, 43, 1),), submit=False)
		doc.append("package_details", {"qty": 5})
		doc.save()
		self.assertEqual(doc.total_packages, 6)

	def test_zero_dimension_gives_zero_cbm_not_an_error(self):
		doc = testing.receipt(self.customer, self.wh, packages=((0, 30, 30, 5),), submit=False)
		self.assertAlmostEqual(flt(doc.package_details[0].cbm), 0.0, places=6)

	# ── capacity ──────────────────────────────────────────────────────────────────

	def test_submit_consumes_and_cancel_releases(self):
		before = testing.available(self.wh)
		doc = testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 10),))
		self.assertAlmostEqual(testing.available(self.wh), before - 10.0, places=6)

		doc.cancel()
		self.assertAlmostEqual(testing.available(self.wh), before, places=6)

	def test_derived_occupancy_tracks_available(self):
		testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 25),))
		space = capacity.get_capacity(self.wh)
		self.assertAlmostEqual(space.occupied_cbm, 25.0, places=6)
		self.assertAlmostEqual(space.utilisation_pct, 25.0, places=6)
		stored = frappe.db.get_value(
			"Warehouse Unit", self.wh, ["occupied_capacity_cbm", "utilisation_pct"], as_dict=True
		)
		self.assertAlmostEqual(flt(stored.occupied_capacity_cbm), 25.0, places=6)
		self.assertAlmostEqual(flt(stored.utilisation_pct), 25.0, places=6)

	def test_submit_refused_when_warehouse_is_full(self):
		small = testing.warehouse("Tiny", capacity_cbm=5.0)
		doc = testing.receipt(self.customer, small, packages=((100, 100, 100, 50),), submit=False)
		self.assertRaises(frappe.ValidationError, doc.submit)
		# The refusal must not have eaten the space on the way out.
		self.assertAlmostEqual(testing.available(small), 5.0, places=6)

	def test_capacity_is_a_no_op_without_a_warehouse(self):
		"""Carried over from the 2026-09-01 suite, which built a Receipt Note with no
		warehouse. warehouse_unit is mandatory now, so the guard is tested directly."""
		capacity.move_capacity(None, -25.0)
		capacity.move_capacity("", 25.0)
		capacity.move_capacity(self.wh, 0)
		self.assertAlmostEqual(testing.available(self.wh), 100.0, places=6)

	def test_capacity_never_exceeds_total_on_release(self):
		"""A double release means an event fired twice, and is refused rather than
		quietly inflating the warehouse."""
		self.assertRaises(
			frappe.ValidationError, capacity.release, self.wh, 10.0, "test double release"
		)

	# ── numbering and status ──────────────────────────────────────────────────────

	def test_name_comes_from_the_series_not_the_waybill(self):
		doc = testing.receipt(self.customer, self.wh, waybill_no="WB-NAME-CHECK-1")
		self.assertTrue(doc.name.startswith("HSM-WR-"), doc.name)
		self.assertEqual(doc.waybill_no, "WB-NAME-CHECK-1")

	def test_tracking_no_is_generated_and_unique(self):
		a = testing.receipt(self.customer, self.wh)
		b = testing.receipt(self.customer, self.wh)
		self.assertTrue(a.tracking_no)
		self.assertTrue(b.tracking_no)
		self.assertNotEqual(a.tracking_no, b.tracking_no)

	def test_submit_sets_in_warehouse_and_current_location(self):
		doc = testing.receipt(self.customer, self.wh)
		doc.reload()
		self.assertEqual(doc.wms_status, "In Warehouse")
		self.assertEqual(doc.current_warehouse_unit, self.wh)
		self.assertEqual(doc.job_status, "Not Created")

	# ── the constraint that made 3PL the wrong engine ─────────────────────────────

	def test_nothing_touches_the_stock_ledger(self):
		"""Customer cargo is not HSM's, so it is not an Item and never enters stock."""
		sle_before = frappe.db.count("Stock Ledger Entry")
		bin_before = frappe.db.count("Bin")

		doc = testing.receipt(self.customer, self.wh, packages=((100, 100, 100, 3),))
		doc.cancel()

		self.assertEqual(frappe.db.count("Stock Ledger Entry"), sle_before)
		self.assertEqual(frappe.db.count("Bin"), bin_before)
