# Copyright (c) 2026, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ReceiptNote(Document):
	"""Legacy warehouse intake.

	Superseded by the Warehouse 3PL app (ASN -> Receiving -> Putaway). Kept so the
	existing records stay readable and correct while they are migrated across; new
	warehouse work should go through Warehouse 3PL.
	"""

	@property
	def total_package_cbm(self):
		return sum(flt(item.cbm) for item in (self.package_details or []))

	def on_submit(self):
		self.consume_warehouse_capacity()

	def on_cancel(self):
		# Without this the capacity taken on submit was never given back: cancelling or
		# amending a Receipt Note silently lost that space until someone edited the
		# Warehouse Unit by hand.
		self.release_warehouse_capacity()

	def consume_warehouse_capacity(self):
		"""Reduce the linked Warehouse Unit's available capacity by this note's CBM."""
		self._move_capacity(-self.total_package_cbm)

	def release_warehouse_capacity(self):
		"""Give the capacity back."""
		self._move_capacity(self.total_package_cbm)

	def _move_capacity(self, delta):
		if not self.warehouse_unit or not delta:
			return

		# for_update takes a row lock for the rest of the transaction. Two concurrent
		# submits used to read the same starting figure and one update was lost.
		current = flt(
			frappe.db.get_value(
				"Warehouse Unit", self.warehouse_unit, "total_available_capacity", for_update=True
			)
		)
		new_capacity = current + flt(delta)

		if new_capacity < 0:
			frappe.throw(
				_("Not enough available capacity in warehouse {0}. Available {1}, required {2}.").format(
					self.warehouse_unit, current, abs(flt(delta))
				)
			)

		frappe.db.set_value(
			"Warehouse Unit", self.warehouse_unit, "total_available_capacity", new_capacity
		)
