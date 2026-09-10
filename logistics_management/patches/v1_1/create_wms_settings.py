"""Create Warehouse Management Settings, seeded so behaviour does not change on upgrade.

Every value here is what the code used to hardcode. A site that upgrades and never opens
the form gets exactly what it had before; the point is that it can now be changed without
a deploy.

Two deliberate exceptions, both fixing something live:

- `treat_zero_capacity_as_unlimited` is ON. A Warehouse Unit left at 0 has not had its size
  entered, which is not a warehouse of size zero -- and the old guard refused every receipt
  into one. On hsm-erp that is GUANJZHOU, CHINA and YIWU CHINA.
- `enable_monthly_accrual` is OFF. Nothing should start creating documents on a timer at a
  client site without somebody choosing it.
"""

import frappe

from logistics_management.wms.settings import DEFAULTS, SETTINGS

WORKSPACE = "Logistics"
SETUP_CARD = "Warehouse Setup"


def execute():
	if not frappe.db.exists("DocType", SETTINGS):
		return

	doc = frappe.get_single(SETTINGS)
	changed = False

	for fieldname, value in DEFAULTS.items():
		if value is None:
			continue
		if not doc.meta.get_field(fieldname):
			continue
		if doc.get(fieldname) in (None, ""):
			doc.set(fieldname, value)
			changed = True

	# Point at the storage item and unit this site already has, if they differ from the
	# shipped defaults -- an earlier release created them under fixed names.
	for fieldname, doctype in (("storage_item", "Item"), ("storage_uom", "UOM")):
		value = doc.get(fieldname)
		if value and not frappe.db.exists(doctype, value):
			# Named but absent: leave it. _ensure_* creates it on first use.
			continue

	if changed:
		doc.flags.ignore_permissions = True
		doc.flags.ignore_validate = True   # the form's own checks need the UOM to exist
		doc.save()

	_add_settings_link()


def _add_settings_link():
	"""Put the settings on the workspace, next to the other Warehouse Setup masters."""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	if any(row.link_to == SETTINGS for row in ws.links):
		return
	if not any(row.type == "Card Break" and row.label == SETUP_CARD for row in ws.links):
		return

	# Insert directly after the Warehouse Setup card's own links so it lands in that card
	# rather than at the end of the workspace, where it would belong to whatever card
	# comes last.
	idx = None
	for i, row in enumerate(ws.links):
		if row.type == "Card Break" and row.label == SETUP_CARD:
			idx = i
		elif idx is not None and row.type == "Card Break":
			break
		elif idx is not None:
			idx = i

	link = {
		"type": "Link",
		"label": "Warehouse Management Settings",
		"link_type": "DocType",
		"link_to": SETTINGS,
		"hidden": 0,
		"onboard": 0,
		"is_query_report": 0,
	}
	ws.append("links", link)
	if idx is not None:
		rows = ws.links
		rows.insert(idx + 1, rows.pop())
		for i, row in enumerate(rows):
			row.idx = i + 1

	ws.save(ignore_permissions=True)
	frappe.clear_cache()
