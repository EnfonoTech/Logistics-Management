import os

import frappe
from frappe.core.doctype.report.report import Report, get_report_module_dotted_path
from frappe.desk.query_report import get_script as frappe_get_script
from frappe.model.utils import render_include
from frappe.modules import get_module_path, scrub
from frappe.utils import get_html_format

APP_NAME = "logistics_management"


class CustomReport(Report):
	"""Lets `report_override` in hooks.py point a standard report at our own execute()."""

	def execute_module(self, filters):
		report_override = frappe.get_hooks("report_override", {})
		if report_override.get(self.name):
			method_name = report_override.get(self.name)[0]
		else:
			module = self.module or frappe.db.get_value("DocType", self.ref_doctype, "module")
			method_name = get_report_module_dotted_path(module, self.name) + ".execute"
		return frappe.get_attr(method_name)(frappe._dict(filters))


@frappe.whitelist()
def get_script(report_name):
	"""Frappe's own get_script, plus the two path redirects this app needs.

	This used to be a full copy of the upstream function. Frappe moved on and the copy
	did not: it silently stopped returning `filters` and `custom_report_name`, which the
	desk uses to resolve a Custom Report's settings. Delegating and then patching only
	what we actually override means it cannot drift again.
	"""
	result = frappe_get_script(report_name)

	script_path = _override_path("report_override_js", report_name)
	if script_path and os.path.exists(script_path):
		with open(script_path) as f:
			script = f.read()
		script += f"\n\n//# sourceURL={scrub(report_name)}.js"
		result["script"] = render_include(script)

	print_path = _override_path("report_override_html", report_name)
	if print_path:
		html_format = get_html_format(print_path)
		if html_format:
			result["html_format"] = html_format

	return result


def _override_path(hook_name, report_name):
	"""Absolute path for a report_override_js / report_override_html hook entry."""
	entries = frappe.get_hooks(hook_name, {})
	relative = entries.get(report_name)
	if not relative:
		return None
	return os.path.join(frappe.get_app_path(APP_NAME), relative[0])


def get_report_folder(report):
	"""Kept for callers that expect the old helper. Unused by get_script above."""
	module = report.module or frappe.db.get_value("DocType", report.ref_doctype, "module")
	if frappe.get_cached_value("Module Def", module, "custom"):
		return ""
	return os.path.join(get_module_path(module), "report", scrub(report.name))
