"""Give the new delivery settings a row, or a Check that ships as 1 reads as False.

settings.get() falls back to DEFAULTS when a value is None. For a Check it never gets
None: frappe.db.get_single_value ends with cast_fieldtype(df.fieldtype, val), and
cast_fieldtype("Check", None) is cint(None) -- zero. A site whose Single predates the
field therefore reads the opposite of what shipped, silently.

warn_on_expired_licence went live on hsm-erp reading False for exactly this reason. Found
by asking the deployed site what the accessor returned rather than trusting the JSON.

A separate patch from setup_driver_tracking on purpose: that one is already in Patch Log
with skipped = 0, so it will never run again and a fix has to arrive as a new file.
"""

from logistics_management.wms.setup import seed_settings_defaults


def execute():
	seed_settings_defaults()
