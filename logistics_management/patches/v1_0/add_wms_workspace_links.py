"""Give the WMS somewhere to be found.

The Logistics workspace shipped with financial report links only — nothing pointed at
Receipt Note, Job Details, Waybill Console or POD, so staff could only reach any of it
through the awesomebar. A training video cannot teach a route that does not exist.

Additive on purpose: this appends a card to whatever the site already has rather than
shipping a Workspace fixture, because a fixture would overwrite HSM's own arrangement of
that workspace. Idempotent -- it adds only the links that are missing.
"""

import frappe

WORKSPACE = "Logistics"

CARDS = [
	(
		"Warehouse",
		[
			("Receipt Note", "DocType", "Receipt Note"),
			("Job Details", "DocType", "Job Details"),
			("Waybill Console", "DocType", "Waybill Console"),
			("POD", "DocType", "POD"),
		],
	),
	(
		"Warehouse Reports",
		[
			("Waybill Tracking", "Report", "Waybill Tracking"),
			("Warehouse Occupancy", "Report", "Warehouse Occupancy"),
		],
	),
	(
		"Warehouse Setup",
		[
			("Warehouse Unit", "DocType", "Warehouse Unit"),
			("Cargo Type", "DocType", "Cargo Type"),
			("Warehouse Storage Rate", "DocType", "Warehouse Storage Rate"),
			("Storage Charge", "DocType", "Storage Charge"),
		],
	),
]


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	existing_links = {row.link_to for row in ws.links if row.link_to}
	existing_breaks = {row.label for row in ws.links if row.type == "Card Break"}
	added = 0

	for card_label, links in CARDS:
		missing = [l for l in links if l[2] not in existing_links]
		if not missing:
			continue

		if card_label not in existing_breaks:
			ws.append("links", {
				"type": "Card Break",
				"label": card_label,
				"hidden": 0,
				"onboard": 0,
			})

		for label, link_type, link_to in missing:
			# A Report link needs its ref doctype or the workspace renders a dead tile.
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
				row["is_query_report"] = 1
				row["dependencies"] = frappe.db.get_value("Report", link_to, "ref_doctype") or ""
			ws.append("links", row)
			added += 1

	if added:
		ws.save(ignore_permissions=True)
		frappe.clear_cache()
