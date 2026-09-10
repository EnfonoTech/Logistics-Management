# Copyright (c) 2024, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class POD(Document):
	"""Proof of delivery for one waybill.

	Two routes, both of which HSM use: print this blank and have the customer sign it on
	paper, or capture the signature elsewhere. Either way the signed copy comes back here
	as an attachment -- "we get it signed by them, and we upload it in this itself".
	"""

	def validate(self):
		self.set_party_names()
		self.stamp_signed_pod()

	def set_party_names(self):
		"""Fallback for a POD with no waybill console.

		customer_name, shipper_name and number_of_packages fetch from the waybill
		console, and set_fetch_from_value() only runs when that link is set -- so this
		fills them from the job for the older, single-customer PODs.
		"""
		if self.waybill_console or not self.job_details:
			return

		job = frappe.db.get_value(
			"Job Details", self.job_details,
			["job_id", "shipper_name", "number_of_packages"], as_dict=True,
		)
		if not job:
			return
		self.customer_name = self.customer_name or job.job_id
		self.shipper_name = self.shipper_name or job.shipper_name
		self.number_of_packages = self.number_of_packages or job.number_of_packages

	def stamp_signed_pod(self):
		"""wms_pod_received tracks whether the signed copy is actually on the record."""
		received = 1 if self.signed_pod else 0
		if received and not self.wms_delivered_at:
			self.wms_delivered_at = frappe.utils.now()
		self.wms_pod_received = received

	def on_update(self):
		self.mirror_to_waybill_console()

	def mirror_to_waybill_console(self):
		"""Show on the waybill whether its signed POD is in hand."""
		if not self.waybill_console:
			return
		if not frappe.db.exists("Waybill Console", self.waybill_console):
			return
		frappe.db.set_value(
			"Waybill Console",
			self.waybill_console,
			{"wms_collected_by": self.collected_by or ""},
			update_modified=False,
		)
