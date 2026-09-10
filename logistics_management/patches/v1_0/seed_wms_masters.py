"""Seed the package types and cargo classes HSM named.

Package types come straight off their flow chart: PLT / CTN / CAN / DRUM / PCS / NOS /
ROLL / BAG. Cargo classes are the four they price differently: "dangerous cargo, liquid
chemicals, general, and items for cooling".
"""

import frappe

PACKAGE_TYPES = ["PLT", "CTN", "CAN", "DRUM", "PCS", "NOS", "ROLL", "BAG"]

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


def execute():
	for types in PACKAGE_TYPES:
		if not frappe.db.exists("Pallet Types", types):
			frappe.get_doc({"doctype": "Pallet Types", "types": types}).insert(
				ignore_permissions=True
			)

	for cargo in CARGO_TYPES:
		if frappe.db.exists("Cargo Type", cargo["cargo_type"]):
			continue
		doc = frappe.new_doc("Cargo Type")
		doc.update(cargo)
		doc.insert(ignore_permissions=True)
