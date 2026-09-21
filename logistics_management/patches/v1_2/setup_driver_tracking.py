"""Driver and vehicle on a delivery, and somewhere on the workspace to find them.

Two jobs, one patch, because neither is any use without the other: the Custom Field and
the relaxed Vehicle master make the masters fillable, and the workspace links make them
reachable without the awesomebar.

The seeding half also runs from after_install -- a fresh site records every existing patch
as executed WITHOUT running it, so a patch alone would leave a new install with a
mandatory-odometer Vehicle and no default-vehicle field at all.
"""

import frappe

from logistics_management.wms.setup import setup_driver_customisations

WORKSPACE = "Logistics"

NEW_LINKS = [
	("Warehouse Reports", [("Driver Trip Report", "Report", "Driver Trip Report")]),
	("Warehouse Setup", [
		("Driver", "DocType", "Driver"),
		("Vehicle", "DocType", "Vehicle"),
	]),
]


def execute():
	setup_driver_customisations()
	add_workspace_links()


def add_workspace_links():
	"""Additive and idempotent, same as add_wms_workspace_links -- never a Workspace fixture,
	which would overwrite HSM's own arrangement of this workspace."""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	existing_links = {row.link_to for row in ws.links if row.link_to}
	existing_breaks = {row.label for row in ws.links if row.type == "Card Break"}
	added = 0

	for card_label, links in NEW_LINKS:
		missing = [l for l in links if l[2] not in existing_links]
		if not missing:
			continue

		# The card itself may not be there on a site that never ran the earlier patch.
		if card_label not in existing_breaks:
			ws.append("links", {
				"type": "Card Break", "label": card_label, "hidden": 0, "onboard": 0,
			})

		for label, link_type, link_to in missing:
			row = {
				"type": "Link",
				"label": label,
				"link_type": link_type,
				"link_to": link_to,
				"hidden": 0,
				"onboard": 0,
				"is_query_report": 0,
			}
			if link_type == "Report":
				# A Report link with no ref doctype renders a dead tile.
				row["is_query_report"] = 1
				row["dependencies"] = frappe.db.get_value("Report", link_to, "ref_doctype") or ""
			ws.append("links", row)
			added += 1

	if added:
		ws.save(ignore_permissions=True)
		frappe.clear_cache()
