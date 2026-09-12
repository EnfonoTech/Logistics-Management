"""Remove the abandoned duplicate Job Details reports, and give the app's Client Scripts a module.

Thirteen Script Reports on Job Details were near-identical typo variants of three real
ones — "Job Detail Report" / "Job Details Report", four spellings of a metrics report, and
six of a sales-person report. Their folders are deleted from the app in the same commit;
without deleting the records too, `bench migrate` leaves orphans in the Report list that
open to nothing.

**Only the unreferenced ones go.** Anything a Workspace Link or Workspace Shortcut points
at is kept, re-checked here rather than trusted from a survey — note the shortcut LABELLED
"Job Details Metrics" actually targets `Job Details Report`, so going by label would have
deleted the one in use.

The Client Script half is what makes the fixtures scopeable: 8 of 8 carried no module, so
a module filter would have exported none of them. The enabled ones that belong to this app
get stamped so `fixtures` can pick them up by module instead of exporting every Client
Script on the site.
"""

import frappe

MODULE = "Logistics Management"

# Deliberately deleted: unreferenced duplicates whose folders go in the same commit.
DEAD = [
	"JD Report",
	"Job Detail Metrics",
	"Job Detail Report",
	"Job Details Metric",
	"Job Details Metrics",
	"Job Details-Metrics",
	"Reports-Sales Person",
	"Sales Person Report",
	"Sales Person Reports",
	"Sales Persons Report",
	"Sales Persons Reports",
]


def execute():
	_prune_reports()
	_stamp_client_scripts()


def _in_use():
	"""Every report a workspace links or shortcuts to, whatever the label says."""
	used = set()
	for table, field, kind in (
		("tabWorkspace Link", "link_type", "Report"),
		("tabWorkspace Shortcut", "type", "Report"),
	):
		rows = frappe.db.sql(
			f"select link_to from `{table}` where {field} = %s and link_to is not null",  # nosemgrep
			(kind,),
		)
		used |= {r[0] for r in rows if r[0]}
	return used


def _prune_reports():
	used = _in_use()
	for name in DEAD:
		if not frappe.db.exists("Report", name):
			continue
		if name in used:
			# Something started pointing at it after this patch was written. Leave it.
			frappe.log_error(
				f"Report {name} is referenced by a workspace; not deleted",
				"WMS report prune",
			)
			continue
		# A standard report refuses deletion while it claims to be file-backed, and its
		# folder is already gone by the time this runs.
		frappe.db.set_value("Report", name, "is_standard", "No", update_modified=False)
		frappe.delete_doc("Report", name, force=True, ignore_permissions=True,
		                  ignore_missing=True, delete_permanently=True)


def _stamp_client_scripts():
	"""Mark the app's own enabled Client Scripts so the module fixture filter finds them."""
	app_doctypes = set(
		frappe.get_all("DocType", filters={"module": MODULE}, pluck="name")
	)
	# DocTypes this app customises through custom/<doctype>.json count as its own too.
	customised = {"Journal Entry", "Sales Invoice", "Sales Invoice Item", "Quotation",
	              "Customer", "Purchase Invoice", "Purchase Invoice Item", "Payment Entry",
	              "Project", "Packed Item"}

	for cs in frappe.get_all("Client Script", filters={"enabled": 1},
	                         fields=["name", "dt", "module"]):
		if cs.module:
			continue
		if cs.dt in app_doctypes or cs.dt in customised:
			frappe.db.set_value("Client Script", cs.name, "module", MODULE,
			                    update_modified=False)
