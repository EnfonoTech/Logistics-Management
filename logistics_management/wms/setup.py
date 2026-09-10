"""Master data the WMS flow cannot work without.

Called from BOTH after_install and a patch, on purpose. A fresh site marks every
existing patch as executed WITHOUT running it -- correct, since there is no legacy data
to fix, but it means a seed-only patch is recorded as done and never fires. That is how
the 3PL service items came to exist on the demo site and nowhere else. Seeding is
idempotent, so running it twice costs nothing and missing it breaks the module.
"""

import frappe

# Straight off the client's flow chart, item 6.
PACKAGE_TYPES = ["PLT", "CTN", "CAN", "DRUM", "PCS", "NOS", "ROLL", "BAG"]

# The four classes HSM price differently: "dangerous cargo, liquid chemicals, general,
# and items for cooling -- so the rate will never be fixed, each one has its own rate."
CARGO_TYPES = [
	{"cargo_type": "General", "description": "Ordinary dry cargo."},
	{
		"cargo_type": "Dangerous Cargo",
		"is_hazardous": 1,
		"description": "IMDG / hazardous cargo. Priced above general.",
	},
	{
		"cargo_type": "Liquid Chemical",
		"is_hazardous": 1,
		"description": "Liquids in drums or cans, usually chemical.",
	},
	{
		"cargo_type": "Reefer - Cooling",
		"requires_temperature_control": 1,
		"description": "Temperature-controlled cargo.",
	},
]


def seed_masters():
	"""Create the package types and cargo classes if they are not already there."""
	created = {"Pallet Types": [], "Cargo Type": []}

	for types in PACKAGE_TYPES:
		if not frappe.db.exists("Pallet Types", types):
			frappe.get_doc({"doctype": "Pallet Types", "types": types}).insert(
				ignore_permissions=True
			)
			created["Pallet Types"].append(types)

	for cargo in CARGO_TYPES:
		if frappe.db.exists("Cargo Type", cargo["cargo_type"]):
			continue
		doc = frappe.new_doc("Cargo Type")
		doc.update(cargo)
		doc.insert(ignore_permissions=True)
		created["Cargo Type"].append(cargo["cargo_type"])

	return created


def after_install():
	"""Runs on a fresh install, where the seed patch is marked done but never executed."""
	seed_masters()
