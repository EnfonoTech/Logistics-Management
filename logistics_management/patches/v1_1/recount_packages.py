"""Recompute total_packages so existing consignment notes print the right count.

Two things were wrong on printed documents:
  * a wholly blank grid row counted as a package -- "Total No. of Package(s): 3" on a
    note carrying two;
  * the print template counted ROWS and ignored qty entirely, so once staff use qty as
    intended, 24 cartons on one row printed as one package. That half is fixed in the
    template.

This half recomputes the stored figure on every existing receipt, submitted included --
total_packages is read-only and derived, so writing it directly is correct and needs no
amendment of a submitted document.
"""

import frappe
from frappe.utils import cint, flt


def execute():
	if not frappe.db.has_column("Receipt Note", "total_packages"):
		return

	rows = frappe.get_all(
		"Package Details",
		filters={"parenttype": "Receipt Note"},
		fields=["parent", "type", "description", "qty", "length", "width", "height"],
	)

	counts = {}
	for r in rows:
		qty = cint(r.qty) or 1
		blank = not (r.type or (r.description or "").strip()) and not (
			flt(r.length) or flt(r.width) or flt(r.height)
		)
		if blank and qty <= 1:
			continue
		counts[r.parent] = counts.get(r.parent, 0) + qty

	changed = 0
	for name, stored in frappe.get_all(
		"Receipt Note", fields=["name", "total_packages"], as_list=True
	):
		correct = counts.get(name, 0)
		if cint(stored) != correct:
			frappe.db.set_value("Receipt Note", name, "total_packages", correct,
			                    update_modified=False)
			changed += 1

	if changed:
		frappe.db.commit()
