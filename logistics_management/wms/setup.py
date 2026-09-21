"""Master data the WMS flow cannot work without.

Called from BOTH after_install and a patch, on purpose. A fresh site marks every
existing patch as executed WITHOUT running it -- correct, since there is no legacy data
to fix, but it means a seed-only patch is recorded as done and never fires. That is how
the 3PL service items came to exist on the demo site and nowhere else. Seeding is
idempotent, so running it twice costs nothing and missing it breaks the module.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

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


# ERPNext's Vehicle insists on make, model and an odometer reading before it will save.
# That is a fleet-maintenance record; HSM need a plate number to put on a POD, and a
# clerk who cannot produce the odometer of a hired truck must not be stopped from
# recording a delivery. Relaxed to optional -- nothing stops HSM filling them in.
VEHICLE_OPTIONAL = ["make", "model", "last_odometer"]

# Both are still mandatory in core and both have one sensible answer here, so the
# defaults are set rather than the requirement dropped.
VEHICLE_DEFAULTS = {"fuel_type": "Diesel", "uom": "Litre"}


def setup_driver_customisations():
	"""The driver's own vehicle, and a Vehicle master a forwarder can actually fill in.

	Idempotent: create_custom_field and make_property_setter both update in place rather
	than duplicating, so this is safe to run on every migrate.
	"""
	create_custom_field(
		"Driver",
		{
			"fieldname": "wms_default_vehicle",
			"label": "Default Vehicle",
			"fieldtype": "Link",
			"options": "Vehicle",
			"insert_after": "cell_number",
			"description": "Offered first in the Deliver Waybill dialog. Can be overridden per trip.",
		},
	)

	# The POD's Contact No is a Phone field and will not take a bare local number, so say
	# so where the number is typed rather than leaving the POD quietly blank.
	make_property_setter(
		"Driver", "cell_number", "description",
		"Store with the country code, e.g. +974 5551 2345, so it reaches the POD.",
		"Small Text", validate_fields_for_doctype=False,
	)

	for fieldname in VEHICLE_OPTIONAL:
		make_property_setter("Vehicle", fieldname, "reqd", 0, "Check", validate_fields_for_doctype=False)

	for fieldname, value in VEHICLE_DEFAULTS.items():
		# A default pointing at a UOM that does not exist would make every Vehicle throw
		# a link error on save, so only set it once the record is really there.
		if fieldname == "uom" and not frappe.db.exists("UOM", value):
			continue
		make_property_setter(
			"Vehicle", fieldname, "default", value, "Small Text",
			validate_fields_for_doctype=False,
		)


def seed_settings_defaults():
	"""Write the shipped defaults into Singles for any setting that has no row yet.

	🔴 settings.get() falls back to DEFAULTS when the value is None -- and for a Check
	field it never gets None. frappe.db.get_single_value ends with
	cast_fieldtype(df.fieldtype, val), and cast_fieldtype("Check", None) is cint(None),
	which is 0. So a Check that ships as 1 reads as False on every site whose Single
	predates the field, with no error anywhere. warn_on_expired_licence was live on
	hsm-erp reading False before this existed.

	Only fields with no row at all are written, so a setting HSM have deliberately
	switched off is never switched back on.
	"""
	if not frappe.db.exists("DocType", "Warehouse Management Settings"):
		return []

	from logistics_management.wms.settings import DEFAULTS, SETTINGS

	meta = frappe.get_meta(SETTINGS)
	# 🔴 NOT frappe.db.exists("Singles", ...). tabSingles has no name column, so exists()
	# finds nothing and every setting looks unseeded -- which would have overwritten all
	# of HSM's choices with the shipped defaults. get_singles_dict is keyed on exactly the
	# fields that do have a row.
	already = set(frappe.db.get_singles_dict(SETTINGS) or {})
	seeded = []

	for fieldname, value in DEFAULTS.items():
		if value is None or not meta.get_field(fieldname):
			continue
		if fieldname in already:
			continue
		frappe.db.set_single_value(SETTINGS, fieldname, value)
		seeded.append(fieldname)

	if seeded:
		frappe.db.value_cache.pop(SETTINGS, None)
		frappe.clear_cache(doctype=SETTINGS)
	return seeded


def after_install():
	"""Runs on a fresh install, where the seed patch is marked done but never executed."""
	seed_masters()
	setup_driver_customisations()
	seed_settings_defaults()
