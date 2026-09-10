"""One place for every warehouse policy that used to be a Python constant.

Day counting, the dimension unit, the billing item, what happens when a warehouse is full
or a customer has no rate — all of it decides what a customer is charged or whether staff
can work, and none of it belongs in code where changing it needs a deploy.

Every accessor falls back to the value the code used before this existed, so a site whose
Single has not been created yet behaves exactly as it did.
"""

import frappe
from frappe.utils import cint, flt

SETTINGS = "Warehouse Management Settings"

# Divisor from <unit>^3 to cubic metres.
DIMENSION_DIVISORS = {
	"Centimetre": 1_000_000.0,          # 100^3
	"Millimetre": 1_000_000_000.0,      # 1000^3
	"Metre": 1.0,
	"Inch": 61023.744094732284,         # 1 / 0.0254^3
}

# Days added to (out - in). Both days inclusive is the usual commercial convention.
DAY_COUNT_OFFSETS = {
	"Both days inclusive": 1,
	"Charge the day in, not the day out": 0,
	"Exclude both days": -1,
}

DEFAULTS = {
	"dimension_uom": "Centimetre",
	"default_cargo_type": None,
	"default_receipt_mode": "Delivery at Warehouse",
	"default_disposition": "Move to Other Warehouse",
	"tracking_number_series": "HSM-TRK-.YYYY.-.#####",
	"capacity_enforcement": "Block the receipt",
	"treat_zero_capacity_as_unlimited": 1,
	"capacity_warning_threshold": 85.0,
	"default_shipment_mode": "IMPORT",
	"fallback_mode_of_transport": "LAND",
	"storage_item": "WMS-STORAGE",
	"storage_uom": "CBM-Day",
	"day_count_method": "Both days inclusive",
	"minimum_chargeable_days": 0,
	"enable_monthly_accrual": 0,
	"accrual_day_of_month": 1,
	"missing_rate_action": "Report and skip",
}


def get(fieldname):
	"""One setting, falling back to the value the code used before it was configurable."""
	default = DEFAULTS.get(fieldname)
	try:
		value = frappe.db.get_single_value(SETTINGS, fieldname)
	except Exception:
		# The DocType may not exist yet during an install or an early patch.
		return default
	if value is None or value == "":
		return default
	return value


def dimension_divisor():
	"""What to divide length x width x height by to get cubic metres."""
	return DIMENSION_DIVISORS.get(get("dimension_uom"), DIMENSION_DIVISORS["Centimetre"])


def dimension_label():
	"""Short unit name for field labels, e.g. 'cm'."""
	return {
		"Centimetre": "cm", "Millimetre": "mm", "Metre": "m", "Inch": "in",
	}.get(get("dimension_uom"), "cm")


def day_count_offset():
	"""Added to (date out - date in) to get chargeable days."""
	return DAY_COUNT_OFFSETS.get(get("day_count_method"), 1)


def minimum_chargeable_days():
	return max(0, cint(get("minimum_chargeable_days")))


def capacity_enforcement():
	return get("capacity_enforcement")


def zero_capacity_is_unlimited():
	return bool(cint(get("treat_zero_capacity_as_unlimited")))


def capacity_warning_threshold():
	return flt(get("capacity_warning_threshold"))


def stop_on_missing_rate():
	return get("missing_rate_action") == "Stop"
