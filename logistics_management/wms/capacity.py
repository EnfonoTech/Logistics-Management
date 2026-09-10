"""The one place a Warehouse Unit's free space is allowed to move.

Capacity is mutated from four different events (receipt, movement, arrival, delivery),
which is exactly the shape that produced lost updates and double counts before. Every
one of them goes through move_capacity() so the row lock, the non-negative guard and
the derived figures can never disagree with each other.

Naming note: the stored fields are still called total_area_capacity and
total_available_capacity because renaming them would have meant a data migration plus
an unverifiable sweep of site-only Client Scripts. They hold CBM and are labelled CBM.
Read them through the helpers below rather than by name.
"""

import frappe
from frappe import _
from frappe.utils import flt

TOTAL_FIELD = "total_area_capacity"
AVAILABLE_FIELD = "total_available_capacity"


def get_capacity(warehouse_unit):
	"""Total, available, occupied and utilisation for one Warehouse Unit, all CBM."""
	row = frappe.db.get_value(
		"Warehouse Unit", warehouse_unit, [TOTAL_FIELD, AVAILABLE_FIELD], as_dict=True
	)
	if not row:
		frappe.throw(_("Warehouse {0} does not exist").format(warehouse_unit))

	total = flt(row.get(TOTAL_FIELD))
	available = flt(row.get(AVAILABLE_FIELD))
	occupied = total - available

	return frappe._dict(
		total_cbm=total,
		available_cbm=available,
		occupied_cbm=occupied,
		utilisation_pct=(occupied / total * 100.0) if total else 0.0,
	)


def move_capacity(warehouse_unit, delta, context=None):
	"""Shift available capacity by delta CBM. Positive frees space, negative consumes it.

	for_update holds a row lock for the rest of the transaction, so two concurrent
	submits cannot both read the same starting figure and lose one of the updates.
	"""
	delta = flt(delta)
	if not warehouse_unit or not delta:
		return

	available = flt(
		frappe.db.get_value("Warehouse Unit", warehouse_unit, AVAILABLE_FIELD, for_update=True)
	)
	new_available = available + delta

	if new_available < 0:
		frappe.throw(
			_("Not enough space in warehouse {0}. Available {1} CBM, required {2} CBM.{3}").format(
				warehouse_unit,
				frappe.format_value(available, {"fieldtype": "Float"}),
				frappe.format_value(abs(delta), {"fieldtype": "Float"}),
				f" ({context})" if context else "",
			),
			title=_("Warehouse Full"),
		)

	total = flt(frappe.db.get_value("Warehouse Unit", warehouse_unit, TOTAL_FIELD))
	if total and new_available > total:
		# Releasing more than was ever taken means an event fired twice. Refuse rather
		# than quietly inflating the warehouse.
		frappe.throw(
			_("Releasing {0} CBM would put warehouse {1} above its total capacity of {2} CBM."
			  " This usually means the same movement was released twice.{3}").format(
				frappe.format_value(delta, {"fieldtype": "Float"}),
				warehouse_unit,
				frappe.format_value(total, {"fieldtype": "Float"}),
				f" ({context})" if context else "",
			),
			title=_("Capacity Release Rejected"),
		)

	occupied = total - new_available
	frappe.db.set_value(
		"Warehouse Unit",
		warehouse_unit,
		{
			AVAILABLE_FIELD: new_available,
			# Derived, stored here rather than computed on read so the list view and the
			# occupancy report can sort and filter on them. This function is the only
			# writer of available capacity, so they cannot fall out of step.
			"occupied_capacity_cbm": occupied,
			"utilisation_pct": (occupied / total * 100.0) if total else 0.0,
		},
		update_modified=False,
	)


def consume(warehouse_unit, cbm, context=None):
	"""Take cbm CBM of space in a warehouse."""
	move_capacity(warehouse_unit, -flt(cbm), context=context)


def release(warehouse_unit, cbm, context=None):
	"""Give cbm CBM of space back."""
	move_capacity(warehouse_unit, flt(cbm), context=context)


@frappe.whitelist()
def get_capacity_for_display(warehouse_unit):
	"""Read-only capacity figures for the Receipt Note form.

	Whitelisted, so it is a public HTTP endpoint and carries its own permission check.
	"""
	frappe.has_permission("Warehouse Unit", "read", throw=True)
	return get_capacity(warehouse_unit)
