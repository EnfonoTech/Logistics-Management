# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from logistics_management.wms import settings


class WarehouseManagementSettings(Document):
	"""Warehouse policy. Changing anything here changes what customers are charged."""

	def validate(self):
		self.validate_thresholds()
		self.validate_tracking_series()
		self.validate_storage_uom()

	def validate_thresholds(self):
		if not 0 <= flt(self.capacity_warning_threshold) <= 100:
			frappe.throw(_("Utilisation warning threshold must be between 0 and 100."))
		if cint(self.minimum_chargeable_days) < 0:
			frappe.throw(_("Minimum chargeable days cannot be negative."))
		if not 1 <= cint(self.accrual_day_of_month) <= 28:
			# 29-31 would skip February entirely in some years.
			frappe.throw(
				_("Accrual day of month must be between 1 and 28, so it runs in every month.")
			)

	def validate_tracking_series(self):
		if not (self.tracking_number_series or "").strip():
			frappe.throw(_("Tracking number series cannot be blank."))
		if "#" not in self.tracking_number_series:
			frappe.throw(
				_("Tracking number series {0} has no # placeholder, so every receipt would"
				  " get the same number.").format(frappe.bold(self.tracking_number_series))
			)

	def validate_storage_uom(self):
		"""A whole-number UOM makes every storage invoice fail.

		CBM-days are almost never whole -- 6.48 CBM for 31 days is 200.88 -- and ERPNext
		refuses a fractional quantity on a UOM flagged must_be_whole_number.
		"""
		if not self.storage_uom:
			return
		if frappe.db.get_value("UOM", self.storage_uom, "must_be_whole_number"):
			frappe.throw(
				_("UOM {0} must allow fractions to be used for storage. Untick"
				  " 'Must be Whole Number' on it, or choose another unit — otherwise every"
				  " storage invoice fails with a fractional quantity.").format(
					frappe.bold(self.storage_uom)
				),
				title=_("Whole-number UOM"),
			)


@frappe.whitelist()
def get_receipt_defaults():
	"""Defaults for a new Receipt Note. Public endpoint, so it checks its own permission."""
	frappe.has_permission("Receipt Note", "create", throw=True)
	return frappe._dict(
		cargo_type=settings.get("default_cargo_type"),
		receipt_mode=settings.get("default_receipt_mode"),
		disposition=settings.get("default_disposition"),
		dimension_label=settings.dimension_label(),
		warning_threshold=settings.capacity_warning_threshold(),
	)
