# Copyright (c) 2026, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt

from logistics_management.wms import capacity
from logistics_management.wms.movement import (
	STATUS_DELIVERED,
	STATUS_IN_MOVEMENT,
	STATUS_IN_WAREHOUSE,
)

CBM_PER_CUBIC_CM = 1000000.0


class ReceiptNote(Document):
	"""Goods received into a warehouse from a customer, against one waybill.

	This is a freight forwarder's warehouse: the cargo is not HSM's, so nothing here is
	an Item and nothing touches the Stock Ledger. The unit of record is the waybill and
	the unit of measure is CBM, computed from package dimensions and counts.
	"""

	def validate(self):
		self.calculate_package_cbm()
		self.sync_shipper_name()
		self.warn_if_over_capacity()

	def before_submit(self):
		self.set_tracking_no()

	def on_submit(self):
		self.db_set(
			{
				"wms_status": STATUS_IN_WAREHOUSE,
				"current_warehouse_unit": self.warehouse_unit,
				"job_status": "Not Created",
			},
			update_modified=False,
		)
		capacity.consume(
			self.warehouse_unit, self.total_cbm, context=_("receipt {0}").format(self.name)
		)

	def on_cancel(self):
		# Without this the space taken on submit was never given back: cancelling or
		# amending silently lost it until someone edited the Warehouse Unit by hand.
		if self.wms_status in (STATUS_IN_MOVEMENT, STATUS_DELIVERED):
			frappe.throw(
				_("This receipt is {0}. Cancel the movement job first.").format(self.wms_status),
				title=_("Cannot Cancel"),
			)
		capacity.release(
			self.warehouse_unit, self.total_cbm, context=_("cancelled receipt {0}").format(self.name)
		)
		self.db_set(
			{"wms_status": None, "current_warehouse_unit": None}, update_modified=False
		)

	# ── calculation ────────────────────────────────────────────────────────────────

	def calculate_package_cbm(self):
		"""Row CBM is length x width x height / 1e6 x qty, and the total is their sum.

		Mirrors receipt_note.js so a server-side insert, a data import and the desk all
		agree. Before this, qty did not exist and one row meant exactly one package.
		"""
		total_cbm = 0.0
		total_packages = 0

		for row in self.package_details or []:
			qty = cint(row.qty) or 1
			row.qty = qty
			unit_cbm = (
				flt(row.length) * flt(row.width) * flt(row.height) / CBM_PER_CUBIC_CM
				if flt(row.length) > 0 and flt(row.width) > 0 and flt(row.height) > 0
				else 0.0
			)
			row.cbm = unit_cbm * qty
			total_cbm += row.cbm
			total_packages += qty

		self.total_cbm = total_cbm
		self.total_packages = total_packages

	@property
	def total_package_cbm(self):
		"""Kept for callers that used it before total_cbm was trustworthy."""
		return sum(flt(row.cbm) for row in (self.package_details or []))

	def sync_shipper_name(self):
		"""A one-off shipper is typed; a known Supplier fills its own name."""
		if self.shipper and not self.shipper_name:
			self.shipper_name = frappe.db.get_value("Supplier", self.shipper, "supplier_name")

	def warn_if_over_capacity(self):
		"""Say so while the form is open, not only at submit.

		on_submit still refuses through capacity.consume() -- that is the hard gate. This
		is the early warning HSM asked for: "before entering, we can see the space".
		"""
		if self.docstatus != 0 or not self.warehouse_unit or flt(self.total_cbm) <= 0:
			return

		space = capacity.get_capacity(self.warehouse_unit)
		self.wh_total_cbm = space.total_cbm
		self.wh_available_cbm = space.available_cbm
		self.wh_utilisation_pct = space.utilisation_pct

		if space.total_cbm and flt(self.total_cbm) > space.available_cbm:
			frappe.msgprint(
				_("{0} CBM will not fit in {1} -- only {2} CBM is free.").format(
					flt(self.total_cbm), self.warehouse_unit, space.available_cbm
				),
				title=_("Warehouse Nearly Full"),
				indicator="orange",
			)

	# ── numbering ──────────────────────────────────────────────────────────────────

	def set_tracking_no(self):
		"""The number handed to the customer for status lookups.

		Separate from waybill_no, which is HSM's own hand-entered consignment number and
		which they confirmed is correct as it stands.
		"""
		if self.tracking_no:
			return
		self.tracking_no = make_autoname("HSM-TRK-.YYYY.-.#####")
