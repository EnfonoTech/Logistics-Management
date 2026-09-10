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
		self.stamp_signed_pod()

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
