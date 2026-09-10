# Copyright (c) 2026, Enfono Technologies and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from logistics_management.wms import storage_billing, testing
from logistics_management.wms.storage_billing import chargeable_days


class TestStorageCharge(FrappeTestCase):
	def setUp(self):
		self.customer = testing.customer("Storage")
		self.wh = testing.warehouse("Storage", capacity_cbm=1000.0)
		testing.cargo_type("General")
		frappe.db.delete("Storage Charge", {"customer": self.customer})
		frappe.db.delete("Warehouse Storage Rate", {"customer": self.customer})
		testing.storage_rate(self.customer, "General", rate=3.0, valid_from="2020-01-01")

	# ── day counting ──────────────────────────────────────────────────────────────

	def test_days_are_inclusive_of_both_ends(self):
		"""Stored 1st to 12th inclusive is 12 days, which is the commercial convention.
		Stated on every Storage Charge so HSM can check the reading."""
		days, start, end = chargeable_days("2026-08-01", "2026-08-12", "2026-08-01", "2026-08-31")
		self.assertEqual(days, 12)
		self.assertEqual(str(start), "2026-08-01")
		self.assertEqual(str(end), "2026-08-12")

	def test_a_stay_still_running_is_charged_to_the_period_end(self):
		days, _, end = chargeable_days("2026-08-20", None, "2026-08-01", "2026-08-31")
		self.assertEqual(days, 12)
		self.assertEqual(str(end), "2026-08-31")

	def test_a_stay_starting_before_the_period_is_clipped(self):
		days, start, _ = chargeable_days("2026-07-15", None, "2026-08-01", "2026-08-31")
		self.assertEqual(days, 31)
		self.assertEqual(str(start), "2026-08-01")

	def test_a_stay_ending_before_the_period_charges_nothing(self):
		days, _, _ = chargeable_days("2026-06-01", "2026-06-30", "2026-08-01", "2026-08-31")
		self.assertEqual(days, 0)

	# ── accrual ───────────────────────────────────────────────────────────────────

	def _stored_receipt(self, cbm_qty=19, cons_date="2026-08-01"):
		return testing.receipt(
			self.customer, self.wh,
			packages=((100, 100, 100, cbm_qty),),
			disposition="Store at Same Warehouse",
			cons_date=cons_date,
		)

	def test_accrual_prices_the_worked_example(self):
		"""19 CBM, 12 days, QAR 3.00 per CBM per day -> QAR 684.00."""
		receipt = self._stored_receipt(cbm_qty=19, cons_date="2026-08-01")
		frappe.db.set_value("Receipt Note", receipt.name, "wms_delivery_date", "2026-08-12",
		                    update_modified=False)

		result = storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		charge_name = frappe.db.get_value(
			"Storage Charge", {"receipt_note": receipt.name, "period_start": "2026-08-01"}, "name"
		)
		self.assertTrue(charge_name, f"no charge generated; skipped={result.skipped}")

		charge = frappe.get_doc("Storage Charge", charge_name)
		self.assertEqual(charge.days, 12)
		self.assertAlmostEqual(flt(charge.cbm), 19.0, places=3)
		self.assertAlmostEqual(flt(charge.amount), 684.0, places=2)

	def test_accrual_is_idempotent(self):
		receipt = self._stored_receipt(cbm_qty=5, cons_date="2026-08-01")
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		self.assertEqual(
			frappe.db.count("Storage Charge",
			                {"receipt_note": receipt.name, "period_start": "2026-08-01"}),
			1,
		)

	def test_a_moving_consignment_is_not_charged_storage(self):
		"""Only Store at Same Warehouse accrues rent."""
		moving = testing.receipt(
			self.customer, self.wh, packages=((100, 100, 100, 5),),
			disposition="Move to Other Warehouse", cons_date="2026-08-01",
		)
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		self.assertEqual(frappe.db.count("Storage Charge", {"receipt_note": moving.name}), 0)

	def test_a_missing_rate_is_reported_not_silently_zero(self):
		"""The 3PL failure was a missing rate producing no billing row and no complaint."""
		other = testing.customer("NoRate")
		frappe.db.delete("Warehouse Storage Rate", {"customer": other})
		receipt = testing.receipt(
			other, self.wh, packages=((100, 100, 100, 4),),
			disposition="Store at Same Warehouse", cons_date="2026-08-01",
		)

		result = storage_billing.generate_storage_charges("2026-08-01", "2026-08-31",
		                                                  customer=other)
		self.assertEqual(frappe.db.count("Storage Charge", {"receipt_note": receipt.name}), 0)
		self.assertTrue(
			any(receipt.name == name for name, _reason in result.skipped),
			f"missing rate was not reported: {result.skipped}",
		)

	def test_one_missing_rate_does_not_abort_the_whole_month(self):
		payer = self._stored_receipt(cbm_qty=3, cons_date="2026-08-01")
		other = testing.customer("NoRate2")
		frappe.db.delete("Warehouse Storage Rate", {"customer": other})
		testing.receipt(
			other, self.wh, packages=((100, 100, 100, 4),),
			disposition="Store at Same Warehouse", cons_date="2026-08-01",
		)

		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		self.assertTrue(frappe.db.exists("Storage Charge", {"receipt_note": payer.name}))

	# ── invoicing ─────────────────────────────────────────────────────────────────

	def test_invoice_accepts_a_fractional_cbm_day_quantity(self):
		"""CBM-days are almost never whole, and ERPNext refuses fractions on Nos.

		6.48 CBM stored 31 days is 200.88 CBM-days, which raised
		UOMMustBeIntegerError until the storage item moved to a CBM-Day UOM.
		"""
		receipt = self._stored_receipt(cbm_qty=6, cons_date="2026-08-01")
		frappe.db.set_value("Receipt Note", receipt.name, "wms_delivery_date", "2026-08-12",
		                    update_modified=False)
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")

		invoices = storage_billing.create_storage_invoices(
			"2026-08-01", "2026-08-31", testing.company()
		)
		self.assertTrue(invoices)

		si = frappe.get_doc("Sales Invoice", invoices[0])
		row = si.items[0]
		# 6 CBM x 12 days x QAR 3.00 = 216.00, billed as 72 CBM-days at 3.00
		self.assertEqual(row.uom, "CBM-Day")
		self.assertAlmostEqual(flt(row.qty), 72.0, places=3)
		self.assertAlmostEqual(flt(row.rate), 3.0, places=2)
		self.assertAlmostEqual(flt(row.amount), 216.0, places=2)
		self.assertTrue(row.wms_storage_charge)

	def test_invoice_line_qty_may_be_a_true_fraction(self):
		"""The regression that actually bit: a non-integer quantity."""
		receipt = self._stored_receipt(cbm_qty=1, cons_date="2026-08-01")
		frappe.db.sql(
			"update `tabReceipt Note` set total_cbm = 6.48 where name = %s", (receipt.name,)
		)
		frappe.db.set_value("Receipt Note", receipt.name, "wms_delivery_date", "2026-08-31",
		                    update_modified=False)
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")

		invoices = storage_billing.create_storage_invoices(
			"2026-08-01", "2026-08-31", testing.company()
		)
		si = frappe.get_doc("Sales Invoice", invoices[0])
		qty = flt(si.items[0].qty)
		self.assertAlmostEqual(qty, 6.48 * 31, places=2)
		self.assertNotEqual(qty, int(qty), "the quantity under test must be fractional")

	def test_charges_are_stamped_on_submit_and_released_on_cancel(self):
		"""The traceability warehouse_3pl's Billing Transaction never had."""
		receipt = self._stored_receipt(cbm_qty=4, cons_date="2026-08-01")
		frappe.db.set_value("Receipt Note", receipt.name, "wms_delivery_date", "2026-08-10",
		                    update_modified=False)
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		invoices = storage_billing.create_storage_invoices(
			"2026-08-01", "2026-08-31", testing.company()
		)

		si = frappe.get_doc("Sales Invoice", invoices[0])
		si.submit()
		charges = frappe.get_all("Storage Charge", filters={"sales_invoice": si.name},
		                         fields=["name", "invoiced"])
		self.assertTrue(charges)
		self.assertTrue(all(c.invoiced for c in charges))

		si.cancel()
		released = frappe.get_all("Storage Charge", filters={"name": ["in", [c.name for c in charges]]},
		                          fields=["invoiced"])
		self.assertFalse(any(c.invoiced for c in released))

	def test_invoicing_twice_finds_nothing_to_bill(self):
		receipt = self._stored_receipt(cbm_qty=4, cons_date="2026-08-01")
		frappe.db.set_value("Receipt Note", receipt.name, "wms_delivery_date", "2026-08-10",
		                    update_modified=False)
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		storage_billing.create_storage_invoices("2026-08-01", "2026-08-31", testing.company())
		self.assertRaises(
			frappe.ValidationError, storage_billing.create_storage_invoices,
			"2026-08-01", "2026-08-31", testing.company(),
		)

	# ── the invoiced guard ────────────────────────────────────────────────────────

	def test_amount_is_always_recomputed_from_the_inputs(self):
		receipt = self._stored_receipt(cbm_qty=10, cons_date="2026-08-01")
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		charge = frappe.get_doc(
			"Storage Charge",
			frappe.db.get_value("Storage Charge", {"receipt_note": receipt.name}, "name"),
		)
		charge.amount = 1.0
		charge.save()
		self.assertAlmostEqual(
			flt(charge.amount),
			flt(charge.cbm) * charge.days * flt(charge.rate_per_cbm_per_day),
			places=2,
		)

	def test_an_invoiced_charge_cannot_be_edited(self):
		receipt = self._stored_receipt(cbm_qty=10, cons_date="2026-08-01")
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		name = frappe.db.get_value("Storage Charge", {"receipt_note": receipt.name}, "name")
		frappe.db.set_value("Storage Charge", name, "invoiced", 1, update_modified=False)

		charge = frappe.get_doc("Storage Charge", name)
		charge.days = 99
		self.assertRaises(frappe.ValidationError, charge.save)

	def test_accrual_leaves_an_invoiced_charge_alone(self):
		receipt = self._stored_receipt(cbm_qty=10, cons_date="2026-08-01")
		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		name = frappe.db.get_value("Storage Charge", {"receipt_note": receipt.name}, "name")
		frappe.db.set_value("Storage Charge", name,
		                    {"invoiced": 1, "amount": 999.0}, update_modified=False)

		storage_billing.generate_storage_charges("2026-08-01", "2026-08-31")
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Storage Charge", name, "amount")), 999.0, places=2
		)
