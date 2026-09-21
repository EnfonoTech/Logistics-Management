# Copyright (c) 2026, Enfono Technologies and contributors
# See license.txt

"""Trips are not deliveries, and that distinction is the whole report.

HSM asked for "the report of his total trip". One driver taking three waybills out in one
truck on one morning has made one trip. Counting rows would say three and inflate every
driver's day, so it is tested directly.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from logistics_management.logistics_management.report.driver_trip_report import (
	driver_trip_report as report,
)
from logistics_management.wms import consolidation, movement, testing


class TestDriverTripReport(FrappeTestCase):
	def setUp(self):
		self.origin = testing.warehouse("TripOrigin", capacity_cbm=500.0)
		self.destination = testing.warehouse("TripDest", capacity_cbm=500.0)
		self.customer = testing.customer("Trip")
		self.driver = testing.driver("Trip")
		self.other_driver = testing.driver("TripOther")
		self.van = testing.vehicle("TEST-TRIP-VAN")

	def _deliver(self, driver=None, vehicle=None, delivery_date=None, cbm_qty=1, mode="Delivery"):
		receipt = testing.receipt(
			self.customer, self.origin, packages=((100, 100, 100, cbm_qty),)
		)
		result = consolidation.create_console_job_from_receipts(
			[receipt.name], destination_warehouse=self.destination
		)
		movement.confirm_arrival(result.job)
		movement.record_delivery(
			result.waybill_consoles[0],
			delivery_date=delivery_date or nowdate(),
			delivery_mode=mode,
			driver=driver,
			vehicle=vehicle,
			create_pod=0,
		)
		return result.waybill_consoles[0]

	def _run(self, **filters):
		filters.setdefault("from_date", add_days(nowdate(), -30))
		filters.setdefault("to_date", add_days(nowdate(), 1))
		return report.execute(filters)

	def test_three_waybills_one_van_one_day_is_one_trip(self):
		for _ in range(3):
			self._deliver(driver=self.driver, vehicle=self.van)

		_cols, data, _msg, _chart, summary = self._run(driver=self.driver)

		self.assertEqual(len(data), 3)
		self.assertEqual(report.count_trips(data), 1)
		by_label = {row["label"]: row["value"] for row in summary}
		self.assertEqual(by_label["Trips"], 1)
		self.assertEqual(by_label["Deliveries"], 3)

	def test_the_same_van_on_two_days_is_two_trips(self):
		self._deliver(driver=self.driver, vehicle=self.van, delivery_date=nowdate())
		self._deliver(driver=self.driver, vehicle=self.van, delivery_date=add_days(nowdate(), -1))

		_cols, data, _msg, _chart, _summary = self._run(driver=self.driver)
		self.assertEqual(report.count_trips(data), 2)

	def test_two_vans_on_one_day_is_two_trips(self):
		second = testing.vehicle("TEST-TRIP-VAN-2")
		self._deliver(driver=self.driver, vehicle=self.van)
		self._deliver(driver=self.driver, vehicle=second)

		_cols, data, _msg, _chart, _summary = self._run(driver=self.driver)
		self.assertEqual(report.count_trips(data), 2)

	def test_a_delivery_with_no_driver_is_not_a_trip_but_is_still_a_row(self):
		"""Every delivery recorded before this feature existed has no driver. They must
		still appear -- that is the backlog HSM has to chase -- but they cannot be counted
		as somebody's trip."""
		self._deliver(driver=None, vehicle=None)

		_cols, data, _msg, _chart, summary = self._run(only_undriven=1)

		self.assertTrue(data)
		self.assertEqual(report.count_trips(data), 0)
		by_label = {row["label"]: row["value"] for row in summary}
		self.assertEqual(by_label["No Driver Recorded"], len(data))

	def test_the_date_filter_excludes_deliveries_outside_it(self):
		old = self._deliver(driver=self.driver, vehicle=self.van,
		                    delivery_date=add_days(nowdate(), -20))
		recent = self._deliver(driver=self.driver, vehicle=self.van, delivery_date=nowdate())

		_cols, data, _msg, _chart, _summary = self._run(
			driver=self.driver, from_date=add_days(nowdate(), -2), to_date=nowdate()
		)
		names = {row["name"] for row in data}
		self.assertIn(recent, names)
		self.assertNotIn(old, names)

	def test_rows_carry_the_cbm_the_customer_and_the_vehicle(self):
		console = self._deliver(driver=self.driver, vehicle=self.van, cbm_qty=4)

		_cols, data, _msg, _chart, _summary = self._run(driver=self.driver)
		row = next(r for r in data if r["name"] == console)

		self.assertEqual(row["customer"], self.customer)
		self.assertEqual(row["wms_vehicle"], self.van)
		self.assertEqual(row["driver_name"], f"{testing.PREFIX} Driver Trip")
		self.assertAlmostEqual(flt(row["total_cbm"]), 4.0, places=6)
		self.assertEqual(row["wms_delivery_mode"], "Delivery")

	def test_one_driver_does_not_see_anothers_deliveries(self):
		mine = self._deliver(driver=self.driver, vehicle=self.van)
		theirs = self._deliver(driver=self.other_driver, vehicle=self.van)

		_cols, data, _msg, _chart, _summary = self._run(driver=self.driver)
		names = {row["name"] for row in data}
		self.assertIn(mine, names)
		self.assertNotIn(theirs, names)

	def test_the_chart_counts_trips_not_rows(self):
		for _ in range(3):
			self._deliver(driver=self.driver, vehicle=self.van)

		_cols, _data, _msg, chart, _summary = self._run(driver=self.driver)
		self.assertEqual(chart["datasets"][0]["values"], [1])

	def test_an_empty_range_returns_no_summary_rather_than_zeroes(self):
		_cols, data, _msg, chart, summary = self._run(
			from_date=add_days(nowdate(), -400), to_date=add_days(nowdate(), -390)
		)
		self.assertEqual(data, [])
		self.assertIsNone(summary)
		self.assertIsNone(chart)

	def test_a_collection_is_reported_as_a_collection(self):
		console = self._deliver(driver=self.driver, vehicle=self.van, mode="Collection")

		_cols, data, _msg, _chart, _summary = self._run(delivery_mode="Collection")
		row = next(r for r in data if r["name"] == console)
		self.assertEqual(row["wms_delivery_mode"], "Collection")
