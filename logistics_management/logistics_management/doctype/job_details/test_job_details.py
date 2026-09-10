# Copyright (c) 2026, siva and contributors
# See license.txt

"""Consolidation, arrival and delivery.

The headline case is test_one_job_holds_many_customers. HSM said it three times on
2026-09-05, and the code that shipped before this validated against it.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from logistics_management.wms import consolidation, movement, testing


class TestJobDetails(FrappeTestCase):
	def setUp(self):
		self.origin = testing.warehouse("Origin", capacity_cbm=500.0)
		self.destination = testing.warehouse("Destination", capacity_cbm=500.0)
		self.a = testing.customer("A")
		self.b = testing.customer("B")
		self.c = testing.customer("C")

	def _receipt(self, cust, cbm_qty=10, **kw):
		"""One 1x1x1 m package repeated cbm_qty times, so total_cbm == cbm_qty."""
		return testing.receipt(cust, self.origin, packages=((100, 100, 100, cbm_qty),), **kw)

	# ── the requirement ───────────────────────────────────────────────────────────

	def test_one_job_holds_many_customers(self):
		"""Eight waybills across three customers become ONE job with eight rows.

		"No, multiple customers must come in a single job... we bring it in a single
		container, so its cost comes as a single one."
		"""
		customers = [self.a, self.b, self.c, self.a, self.b, self.c, self.a, self.b]
		receipts = [self._receipt(cust, cbm_qty=1) for cust in customers]

		result = consolidation.create_console_job_from_receipts(
			[r.name for r in receipts],
			mode_of_transport="SEA",
			destination_warehouse=self.destination,
		)

		job = frappe.get_doc("Job Details", result.job)
		self.assertEqual(job.job_type, "CONSOLE")
		self.assertEqual(len(job.console_shipment), 8)
		self.assertEqual(len({row.customer for row in job.console_shipment}), 3)
		# Rows never merge and jobs never split.
		self.assertEqual(len(result.waybill_consoles), 8)

	def test_same_customer_twice_still_one_job_two_rows(self):
		receipts = [self._receipt(self.a, cbm_qty=1), self._receipt(self.a, cbm_qty=1)]
		result = consolidation.create_console_job_from_receipts(
			[r.name for r in receipts], destination_warehouse=self.destination
		)
		job = frappe.get_doc("Job Details", result.job)
		self.assertEqual(len(job.console_shipment), 2)

	def test_job_header_carries_company_not_a_customer(self):
		""""When we create a job it should be a job in our name, in the company's name."

		job_id is a Link to Customer despite the name, so a console job leaves it blank.
		"""
		receipts = [self._receipt(self.a, cbm_qty=1), self._receipt(self.b, cbm_qty=1)]
		result = consolidation.create_console_job_from_receipts(
			[r.name for r in receipts], destination_warehouse=self.destination
		)
		job = frappe.get_doc("Job Details", result.job)
		self.assertEqual(job.company, testing.company())
		self.assertFalse(job.job_id)

	def test_waybill_consoles_are_created_from_the_receipts(self):
		"""They used to be typed by hand. Customer, volume and packages come across."""
		receipt = self._receipt(self.a, cbm_qty=7)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.customer, self.a)
		self.assertEqual(console.waybill_no, receipt.waybill_no)
		self.assertEqual(console.job_details, result.job)
		self.assertEqual(console.wms_receipt_note, receipt.name)
		self.assertEqual(flt(console.volume), 7.0)
		self.assertEqual(console.no_of_packages, "7")
		self.assertTrue(console.name.startswith("WBC-"), console.name)

		receipt.reload()
		self.assertEqual(receipt.wms_waybill_console, console.name)
		self.assertEqual(receipt.wms_status, "In Movement")
		self.assertEqual(receipt.job_status, "Created")

	def test_existing_waybill_console_is_reused_not_duplicated(self):
		"""waybill_no is unique, so a blind insert would fail on exactly the records
		HSM already typed by hand."""
		receipt = self._receipt(self.a, cbm_qty=2, waybill_no="WB-PRE-EXISTING-1")
		frappe.get_doc({
			"doctype": "Waybill Console",
			"waybill_no": "WB-PRE-EXISTING-1",
			"customer": self.a,
		}).insert(ignore_permissions=True)

		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		self.assertEqual(
			frappe.db.count("Waybill Console", {"waybill_no": "WB-PRE-EXISTING-1"}), 1
		)
		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.job_details, result.job)

	# ── refusals ──────────────────────────────────────────────────────────────────

	def test_storage_flagged_receipts_are_refused(self):
		stored = self._receipt(self.a, cbm_qty=1, disposition="Store at Same Warehouse")
		self.assertRaises(
			frappe.ValidationError,
			consolidation.create_console_job_from_receipts,
			[stored.name],
			destination_warehouse=self.destination,
		)

	def test_two_origins_are_refused(self):
		other_origin = testing.warehouse("OtherOrigin", capacity_cbm=100.0)
		here = self._receipt(self.a, cbm_qty=1)
		there = testing.receipt(self.b, other_origin, packages=((100, 100, 100, 1),))
		self.assertRaises(
			frappe.ValidationError,
			consolidation.create_console_job_from_receipts,
			[here.name, there.name],
			destination_warehouse=self.destination,
		)

	def test_jobbing_twice_is_refused(self):
		receipt = self._receipt(self.a, cbm_qty=3)
		consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		self.assertRaises(
			frappe.ValidationError,
			consolidation.create_console_job_from_receipts,
			[receipt.name],
			destination_warehouse=self.destination,
		)

	def test_unsubmitted_receipts_are_refused(self):
		draft = self._receipt(self.a, cbm_qty=1, submit=False)
		self.assertRaises(
			frappe.ValidationError,
			consolidation.create_console_job_from_receipts,
			[draft.name],
			destination_warehouse=self.destination,
		)

	def test_destination_cannot_equal_origin(self):
		receipt = self._receipt(self.a, cbm_qty=1)
		self.assertRaises(
			frappe.ValidationError,
			consolidation.create_console_job_from_receipts,
			[receipt.name],
			destination_warehouse=self.origin,
		)

	# ── capacity across the legs ──────────────────────────────────────────────────

	def test_capacity_moves_origin_to_destination_to_delivered(self):
		"""10 CBM Dubai to Qatar: origin +10 at movement, destination -10 at arrival,
		destination +10 at delivery. Each leg exactly once."""
		origin_full = testing.available(self.origin)
		dest_full = testing.available(self.destination)

		receipt = self._receipt(self.a, cbm_qty=10)
		self.assertAlmostEqual(testing.available(self.origin), origin_full - 10.0, places=6)

		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		self.assertAlmostEqual(testing.available(self.origin), origin_full, places=6)
		self.assertAlmostEqual(testing.available(self.destination), dest_full, places=6)

		movement.confirm_arrival(result.job, arrival_date=nowdate(), received_by="Tester")
		self.assertAlmostEqual(testing.available(self.destination), dest_full - 10.0, places=6)

		receipt.reload()
		self.assertEqual(receipt.wms_status, "Arrived at Destination")
		self.assertEqual(receipt.current_warehouse_unit, self.destination)

		movement.record_delivery(
			result.waybill_consoles[0], delivery_mode="Collection", collected_by="Driver",
			create_pod=0,
		)
		self.assertAlmostEqual(testing.available(self.destination), dest_full, places=6)

		# The new WMS field, not the legacy delivery_mode: on hsm-erp that legacy field
		# holds transport terms (LAND, DOOR TO DOOR) on 49 of 831 live records, so it
		# stays free text.
		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.wms_delivery_mode, "Collection")
		self.assertTrue(console.wms_delivered)

		receipt.reload()
		self.assertEqual(receipt.wms_status, "Delivered")
		self.assertFalse(receipt.current_warehouse_unit)

	def test_arrival_cannot_be_confirmed_twice(self):
		receipt = self._receipt(self.a, cbm_qty=5)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		movement.confirm_arrival(result.job)
		self.assertRaises(frappe.ValidationError, movement.confirm_arrival, result.job)

	def test_delivery_before_arrival_is_refused(self):
		"""HSM cannot hand over cargo the destination has not acknowledged receiving."""
		receipt = self._receipt(self.a, cbm_qty=5)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		self.assertRaises(
			frappe.ValidationError, movement.record_delivery, result.waybill_consoles[0]
		)

	def test_delivery_cannot_happen_twice(self):
		receipt = self._receipt(self.a, cbm_qty=5)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		movement.confirm_arrival(result.job)
		movement.record_delivery(result.waybill_consoles[0], create_pod=0)
		self.assertRaises(
			frappe.ValidationError, movement.record_delivery, result.waybill_consoles[0]
		)

	def test_arrival_refused_without_a_destination(self):
		receipt = self._receipt(self.a, cbm_qty=1)
		result = consolidation.create_console_job_from_receipts([receipt.name])
		frappe.db.set_value("Job Details", result.job, "wms_destination_warehouse", None,
		                    update_modified=False)
		self.assertRaises(frappe.ValidationError, movement.confirm_arrival, result.job)

	# ── POD ───────────────────────────────────────────────────────────────────────

	def test_delivery_creates_a_pod_for_the_signature(self):
		receipt = self._receipt(self.a, cbm_qty=2)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		movement.confirm_arrival(result.job)
		delivered = movement.record_delivery(
			result.waybill_consoles[0], collected_by="Mr Customer", create_pod=1
		)

		self.assertTrue(delivered.pod)
		pod = frappe.get_doc("POD", delivered.pod)
		self.assertEqual(pod.waybill_console, result.waybill_consoles[0])
		self.assertEqual(pod.customer_name, self.a)
		self.assertEqual(pod.collected_by, "Mr Customer")
		# Nothing signed yet -- that is the point of the flag.
		self.assertFalse(pod.wms_pod_received)

		pod.signed_pod = "/files/test-signed-pod.pdf"
		pod.save()
		self.assertTrue(pod.wms_pod_received)
		self.assertTrue(pod.wms_delivered_at)
