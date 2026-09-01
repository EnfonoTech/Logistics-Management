app_name = "logistics_management"
app_title = "Logistics Management"
app_publisher = "siva"
app_description = "Logistics Management"
app_email = "siva@enfono.in"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/logistics_management/css/logistics_management.css"
# app_include_js = "/assets/logistics_management/js/logistics_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/logistics_management/css/logistics_management.css"
# web_include_js = "/assets/logistics_management/js/logistics_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "logistics_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# Receipt Note's list view script is auto-loaded by Frappe from the doctype folder
# (logistics_management/doctype/receipt_note/receipt_note_list.js). The hook entry that
# used to sit here pointed at public/js/receipt_note_list.js, which has never existed.
# doctype_list_js = {}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "logistics_management/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "logistics_management.utils.jinja_methods",
# 	"filters": "logistics_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "logistics_management.install.before_install"
# after_install = "logistics_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "logistics_management.uninstall.before_uninstall"
# after_uninstall = "logistics_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "logistics_management.utils.before_app_install"
# after_app_install = "logistics_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "logistics_management.utils.before_app_uninstall"
# after_app_uninstall = "logistics_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "logistics_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }
override_doctype_class = {
    "Report": "logistics_management.overrides.CustomReport"
}
# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
# doc_events is for extending ANOTHER app's DocType. Receipt Note and Direct Shipping
# are ours, so their lifecycle hooks now live as methods on their own controller
# classes. Registering them here as well would fire them twice.
# doc_events = {}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"logistics_management.tasks.all"
# 	],
# 	"daily": [
# 		"logistics_management.tasks.daily"
# 	],
# 	"hourly": [
# 		"logistics_management.tasks.hourly"
# 	],
# 	"weekly": [
# 		"logistics_management.tasks.weekly"
# 	],
# 	"monthly": [
# 		"logistics_management.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "logistics_management.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "logistics_management.event.get_events"
# }
override_whitelisted_methods = {
    "frappe.desk.query_report.get_script": "logistics_management.overrides.get_script"
}
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "logistics_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["logistics_management.utils.before_request"]
# after_request = ["logistics_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["logistics_management.utils.before_job"]
# after_job = ["logistics_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"logistics_management.auth.validate"
# ]
report_override_js = {
	"Job Card Summary": "reports/js/custom_job_card_summary.js",
}

# report_override = {
# 	"Profit and Loss Statement": "logistics_management.reports.gross.execute"
# }
# report_override = {
# 	"Profit and Loss Statement": "logistics_management.reports.profit.execute"
# }
report_override = {
	"Profit and Loss Statement": "logistics_management.reports.loss.execute"
}


report_override_html = {
	"Accounts Receivable": "reports/overrides/html/custom_accounts_receivable.html"
}
# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs


# Single fixtures assignment. There used to be a second one near the top of this file
# declaring Workflow / Workflow State; Python kept only the last binding, so those two
# were silently never exported and the active Direct Shipping Workflow existed only in
# the site database. Keep this list as the one and only `fixtures` in the module.
fixtures = [
	"Client Script",
	"Print Format",
	"Report",
	"Property Setter",
	"Workflow",
	"Workflow State",
]