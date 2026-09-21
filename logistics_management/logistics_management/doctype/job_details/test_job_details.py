# Copyright (c) 2026, siva and contributors
# See license.txt

"""Consolidation, arrival and delivery.

The headline case is test_one_job_holds_many_customers. HSM said it three times on
2026-09-05, and the code that shipped before this validated against it.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from logistics_management.logistics_management.doctype.job_details import job_details
from logistics_management.wms import consolidation, movement, testing

SETTINGS = "Warehouse Management Settings"


def _set_setting(**kwargs):
	for key, value in kwargs.items():
		frappe.db.set_single_value(SETTINGS, key, value)
	frappe.clear_cache(doctype=SETTINGS)


class TestJobDetails(FrappeTestCase):
	def setUp(self):
		# Driver policy is off unless a test turns it on, so nothing leaks between them.
		_set_setting(require_driver_on_delivery=0, warn_on_expired_licence=1)
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

	# ── driver and vehicle ────────────────────────────────────────────────────────

	def _arrived(self, cust=None, cbm_qty=1):
		"""A waybill standing at the destination, ready to be handed over."""
		receipt = self._receipt(cust or self.a, cbm_qty=cbm_qty)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		movement.confirm_arrival(result.job)
		return result

	def test_a_vehicle_needs_nothing_but_its_plate(self):
		"""ERPNext wants make, model and an odometer reading before a Vehicle will save.

		A clerk recording a delivery by a hired truck has none of those, so
		setup_driver_customisations relaxes them. If that ever stops being applied this
		is the test that says so, rather than every driver test failing obscurely.
		"""
		plate = testing.vehicle("TEST-PLATE-ONLY")
		doc = frappe.get_doc("Vehicle", plate)
		self.assertEqual(doc.license_plate, plate)
		# Still mandatory in core, so the defaults have to carry them.
		self.assertEqual(doc.fuel_type, "Diesel")

	def test_driver_and_vehicle_land_on_the_console(self):
		result = self._arrived()
		driver = testing.driver("Console")
		van = testing.vehicle("TEST-VAN-1")

		movement.record_delivery(
			result.waybill_consoles[0], driver=driver, vehicle=van, create_pod=0
		)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.wms_driver, driver)
		self.assertEqual(console.wms_vehicle, van)
		# fetch_from does not fire for db.set_value, so record_delivery writes the name.
		self.assertEqual(console.wms_driver_name, f"{testing.PREFIX} Driver Console")

	def test_pod_carries_the_driver_block_that_used_to_print_blank(self):
		"""assigned_driver_name and assigned_vehicle_no are already on the POD print,
		under the Truck Driver Signature line, and nothing has ever written them."""
		result = self._arrived()
		driver = testing.driver("Pod", cell="+97455599887")
		van = testing.vehicle("TEST-VAN-2")

		delivered = movement.record_delivery(
			result.waybill_consoles[0], driver=driver, vehicle=van, create_pod=1
		)

		pod = frappe.get_doc("POD", delivered.pod)
		self.assertEqual(pod.assigned_driver_name, f"{testing.PREFIX} Driver Pod")
		self.assertEqual(pod.assigned_vehicle_no, van)
		self.assertEqual(pod.contact_no, "+97455599887")

	def test_a_local_mobile_leaves_the_pod_phone_blank_rather_than_failing(self):
		"""POD.contact_no is a Phone field and Frappe refuses one it cannot parse.

		Driver.cell_number is free text, so a clerk who types the Qatari number the way it
		is dialled locally must still be able to record the delivery.
		"""
		result = self._arrived()
		driver = testing.driver("LocalMobile", cell="55512345")

		delivered = movement.record_delivery(
			result.waybill_consoles[0], driver=driver, create_pod=1
		)

		pod = frappe.get_doc("POD", delivered.pod)
		self.assertEqual(pod.assigned_driver_name, f"{testing.PREFIX} Driver LocalMobile")
		self.assertFalse(pod.contact_no)

	def test_vehicle_defaults_from_the_drivers_own(self):
		result = self._arrived()
		van = testing.vehicle("TEST-VAN-3")
		driver = testing.driver("Owner", default_vehicle=van)

		movement.record_delivery(result.waybill_consoles[0], driver=driver, create_pod=0)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.wms_vehicle, van)

	def test_an_explicit_vehicle_beats_the_drivers_default(self):
		"""Drivers swap trucks; the one named for this run wins."""
		result = self._arrived()
		usual = testing.vehicle("TEST-VAN-4")
		today = testing.vehicle("TEST-VAN-5")
		driver = testing.driver("Swap", default_vehicle=usual)

		movement.record_delivery(
			result.waybill_consoles[0], driver=driver, vehicle=today, create_pod=0
		)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.wms_vehicle, today)

	def test_delivery_without_a_driver_is_refused_when_hsm_require_one(self):
		result = self._arrived()
		_set_setting(require_driver_on_delivery=1)
		self.assertRaises(
			frappe.ValidationError, movement.record_delivery,
			result.waybill_consoles[0], delivery_mode="Delivery",
		)

	def test_a_collection_never_needs_a_driver(self):
		"""The customer's own truck came for it -- HSM have no driver to name."""
		result = self._arrived()
		_set_setting(require_driver_on_delivery=1)

		movement.record_delivery(
			result.waybill_consoles[0], delivery_mode="Collection",
			collected_by="Customer's man", create_pod=0,
		)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertTrue(console.wms_delivered)
		self.assertFalse(console.wms_driver)

	def test_a_driver_that_does_not_exist_is_refused(self):
		result = self._arrived()
		self.assertRaises(
			frappe.ValidationError, movement.record_delivery,
			result.waybill_consoles[0], driver="NO SUCH DRIVER",
		)

	def test_an_expired_licence_warns_but_still_records_the_delivery(self):
		"""The cargo is already handed over. Refusing the record would only lose it."""
		result = self._arrived()
		driver = testing.driver("Expired", expiry_date="2020-01-01")
		_set_setting(warn_on_expired_licence=1)

		movement.record_delivery(result.waybill_consoles[0], driver=driver, create_pod=0)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertTrue(console.wms_delivered)
		self.assertEqual(console.wms_driver, driver)

	def test_a_driver_who_has_left_still_gets_a_backdated_delivery_recorded(self):
		result = self._arrived()
		driver = testing.driver("Left", status="Left")

		movement.record_delivery(result.waybill_consoles[0], driver=driver, create_pod=0)

		console = frappe.get_doc("Waybill Console", result.waybill_consoles[0])
		self.assertEqual(console.wms_driver, driver)

	# ── job summary ───────────────────────────────────────────────────────────────

	def test_a_job_with_nothing_booked_has_no_margin_rather_than_a_margin_of_zero(self):
		"""Zero revenue is not a zero-margin job, and a card reading 0.0% would say it is."""
		receipt = self._receipt(self.a, cbm_qty=1)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)

		money = job_details.get_job_financials(result.job)

		self.assertEqual(money.revenue, 0)
		self.assertEqual(money.cost, 0)
		self.assertEqual(money.profit, 0)
		self.assertIsNone(money.margin)
		self.assertEqual(money.outstanding, 0)

	def test_the_summary_reports_in_the_job_company_currency(self):
		receipt = self._receipt(self.a, cbm_qty=1)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		job = frappe.get_doc("Job Details", result.job)

		money = job_details.get_job_financials(job.name)

		self.assertEqual(
			money.currency,
			frappe.get_cached_value("Company", job.company, "default_currency"),
		)

	def test_the_summary_refuses_a_job_the_user_cannot_read(self):
		receipt = self._receipt(self.a, cbm_qty=1)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		# Every whitelisted method is a public HTTP endpoint, so the check is on the method
		# and not on whatever called it.
		frappe.set_user("Guest")
		try:
			self.assertRaises(
				frappe.PermissionError, job_details.get_job_financials, result.job
			)
		finally:
			frappe.set_user("Administrator")
