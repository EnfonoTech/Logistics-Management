# Copyright (c) 2024, siva and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DirectShipping(Document):
	def validate(self):
		self.calculate_line_sale_prices()

	def on_update(self):
		# Writing a second document belongs after this one is known-good, not inside
		# validate() where it ran on every keystroke-triggered save.
		self.sync_track_shipping_order()

	def calculate_line_sale_prices(self):
		for d in self.get("freight_order_line") or []:
			if not d.pricing:
				continue
			basis = flt(d.volume) if d.billing_on == "Volume" else flt(d.gross_weight)
			d.sale_price = basis * flt(d.price)

	def sync_track_shipping_order(self):
		values = {
			"source_location": self.loading_port,
			"destination_location": self.discharging_port,
			"transport_carriage": self.transport,
			"status": self.workflow_state,
		}

		existing = frappe.db.get_value("Track Shipping Order", {"name1": self.name}, "name")
		if existing:
			tso = frappe.get_doc("Track Shipping Order", existing)
			tso.update(values)
			tso.save(ignore_permissions=True)
			return

		tso = frappe.get_doc({
			"doctype": "Track Shipping Order",
			"name1": self.name,
			**values,
		})
		tso.insert(ignore_permissions=True)
