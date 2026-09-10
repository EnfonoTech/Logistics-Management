"""Make the WMS workspace cards actually render.

`add_wms_workspace_links` appended the Workspace Link rows and their Card Breaks, which is
necessary but NOT sufficient: in v15 a workspace renders from its `content` JSON block
list, and a card with no `{"type": "card", "data": {"card_name": ...}}` block is invisible.
The Financial Reports card on this workspace renders precisely because it has one.

Caught by a capture dry-run, which could not find any WMS link on the workspace at all.

This is a separate patch on purpose: the earlier one is already recorded in Patch Log with
skipped = 0, and `executed()` means it will never run again — so a fix has to arrive as a
new patch file, not as an edit to that one.
"""

import json

import frappe

WORKSPACE = "Logistics"
CARDS = ["Warehouse", "Warehouse Reports", "Warehouse Setup"]
HEADER = '<span class="h4"><b>Warehouse Management</b></span>'


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)

	try:
		blocks = json.loads(ws.content or "[]")
	except (ValueError, TypeError):
		# A workspace whose content is not parseable is not something a patch should
		# guess at -- leave it and say so.
		frappe.log_error(
			f"{WORKSPACE}.content is not valid JSON; WMS cards not added",
			"WMS workspace content",
		)
		return

	present = {
		b.get("data", {}).get("card_name")
		for b in blocks
		if isinstance(b, dict) and b.get("type") == "card"
	}
	missing = [c for c in CARDS if c not in present]
	if not missing:
		return

	# Only add cards that really have links behind them, so a partial earlier run cannot
	# leave an empty tile on the workspace.
	have_links = {row.label for row in ws.links if row.type == "Card Break"}
	missing = [c for c in missing if c in have_links]
	if not missing:
		return

	if not any(
		isinstance(b, dict) and b.get("type") == "header" and HEADER in (b.get("data", {}).get("text") or "")
		for b in blocks
	):
		blocks.append({"type": "spacer", "data": {"col": 12}})
		blocks.append({"type": "header", "data": {"text": HEADER, "col": 12}})

	for card in missing:
		blocks.append({"type": "card", "data": {"card_name": card, "col": 4}})

	ws.content = json.dumps(blocks)
	ws.save(ignore_permissions=True)
	frappe.clear_cache()
