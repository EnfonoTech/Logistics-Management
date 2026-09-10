# Copyright (c) 2024, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WaybillConsole(Document):
	"""One customer's waybill inside a consolidation job.

	Created automatically from a Receipt Note when the movement job is made -- HSM used
	to type these by hand and asked for them to come "from the system itself".
	"""

	def validate(self):
		self.protect_delivered_record()

	def protect_delivered_record(self):
		"""Once delivered, the commercial facts are fixed."""
		if self.is_new() or not self.wms_delivered:
			return

		before = self.get_doc_before_save()
		if not before or not before.wms_delivered:
			return

		watched = ("customer", "waybill_no", "volume", "no_of_packages", "wms_delivery_date",
		           "wms_receipt_note", "job_details")
		changed = [fld for fld in watched if self.get(fld) != before.get(fld)]
		if changed:
			frappe.throw(
				_("Waybill {0} was delivered on {1}. {2} cannot be changed now.").format(
					self.waybill_no,
					frappe.format(before.wms_delivery_date, "Date"),
					", ".join(_(self.meta.get_label(fld)) for fld in changed),
				),
				title=_("Already Delivered"),
			)
