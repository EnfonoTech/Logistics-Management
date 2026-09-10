# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from logistics_management.wms.rates import calculate_storage_charge


class StorageCharge(Document):
	"""One consignment's storage for one billing period.

	The amount is always recomputed from cbm x days x rate here, so an edited figure
	cannot drift away from what the invoice will say.
	"""

	def validate(self):
		self.block_edit_after_invoicing()
		self.recalculate_amount()

	def block_edit_after_invoicing(self):
		if self.is_new():
			return

		before = self.get_doc_before_save()
		if not before or not cint(before.invoiced):
			return

		watched = ("cbm", "days", "rate_per_cbm_per_day", "minimum_charge", "amount",
		           "period_start", "period_end", "receipt_note", "customer")
		changed = [fld for fld in watched if self.get(fld) != before.get(fld)]
		if changed:
			frappe.throw(
				_("Storage Charge {0} has already been invoiced on {1}. Cancel that invoice"
				  " before changing {2}.").format(
					self.name, before.sales_invoice or _("a Sales Invoice"),
					", ".join(_(self.meta.get_label(fld)) for fld in changed),
				),
				title=_("Already Invoiced"),
			)

	def recalculate_amount(self):
		self.amount = calculate_storage_charge(
			self.cbm, self.days, self.rate_per_cbm_per_day, self.minimum_charge
		)
		if flt(self.amount) <= 0:
			frappe.throw(
				_("Storage charge for {0} works out to zero. Check the volume ({1} CBM),"
				  " the chargeable days ({2}) and the rate.").format(
					self.receipt_note, flt(self.cbm), cint(self.days)
				),
				title=_("Zero Storage Charge"),
			)
