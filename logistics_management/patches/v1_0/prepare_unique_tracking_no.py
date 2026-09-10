"""Clear blank tracking numbers BEFORE the unique index is created.

Receipt Note.tracking_no becomes unique in this release. MySQL allows many NULLs in a
unique index but only one empty string, so any existing rows holding '' would make the
ALTER TABLE fail and abort the whole migrate. This runs pre_model_sync, which is the
only window where that can be fixed.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Receipt Note"):
		return
	if not frappe.db.has_column("Receipt Note", "tracking_no"):
		return

	blanked = frappe.db.sql(
		"""UPDATE `tabReceipt Note` SET tracking_no = NULL
		   WHERE tracking_no IS NOT NULL AND TRIM(tracking_no) = ''"""
	)

	# Duplicates would break the index just as surely. Keep the oldest holder of each
	# value and clear the rest -- backfill_wms_fields then issues them fresh numbers.
	duplicates = frappe.db.sql(
		"""SELECT tracking_no FROM `tabReceipt Note`
		   WHERE tracking_no IS NOT NULL AND TRIM(tracking_no) != ''
		   GROUP BY tracking_no HAVING COUNT(*) > 1""",
		as_dict=True,
	)
	for row in duplicates:
		keep = frappe.db.sql(
			"""SELECT name FROM `tabReceipt Note` WHERE tracking_no = %s
			   ORDER BY creation ASC LIMIT 1""",
			(row.tracking_no,),
		)
		if not keep:
			continue
		frappe.db.sql(
			"""UPDATE `tabReceipt Note` SET tracking_no = NULL
			   WHERE tracking_no = %s AND name != %s""",
			(row.tracking_no, keep[0][0]),
		)

	if blanked or duplicates:
		frappe.db.commit()
