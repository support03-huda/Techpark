app_name = "techpark"
app_title = "TechPark"
app_publisher = "SWSPL"
app_description = "Customer management and CRM."
app_email = "support03@softworld.co.in"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "techpark",
# 		"logo": "/assets/techpark/logo.png",
# 		"title": "TechPark",
# 		"route": "/techpark",
# 		"has_permission": "techpark.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/techpark/css/techpark_workspace_tabs.css"
app_include_js = ["/assets/techpark/js/techpark.js", "/assets/techpark/js/techpark_workspace_tabs.js"]

# Expense Approvals menu only for users who can approve (see techpark/boot.py).
extend_bootinfo = "techpark.boot.extend_bootinfo"

# include js, css files in header of web template
# web_include_css = "/assets/techpark/css/techpark.css"
# web_include_js = "/assets/techpark/js/techpark.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "techpark/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "techpark/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": ["techpark.customer_card.get_customer_card"],
}

# Installation
# ------------

# before_install = "techpark.install.before_install"
after_install = "techpark.install.after_install"

# Install / refresh the "TechPark Today" dashboard panel from techpark/dashboard_block/
after_migrate = ["techpark.dashboard.sync_dashboard_block"]

# Uninstallation
# ------------

# before_uninstall = "techpark.uninstall.before_uninstall"
# after_uninstall = "techpark.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "techpark.utils.before_app_install"
# after_app_install = "techpark.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "techpark.utils.before_app_uninstall"
# after_app_uninstall = "techpark.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "techpark.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "techpark.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["techpark.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# A Sales User sees only their own DVRs; managers and admins see all of them.
# Expenses follow the reporting line (TP Team Member): own, the team's, or all for approvers.
permission_query_conditions = {
	"Daily Visit Report": "techpark.permission.dvr_query_conditions",
	"TP Expense": "techpark.permission.expense_query_conditions",
}

has_permission = {
	"Daily Visit Report": "techpark.permission.dvr_has_permission",
	"TP Expense": "techpark.permission.expense_has_permission",
}

# Refuse changes to entries locked for salespeople.
_lock = {
	"validate": "techpark.permission.check_lock",
	"before_update_after_submit": "techpark.permission.check_lock",
	"before_cancel": "techpark.permission.check_lock",
	"on_trash": "techpark.permission.check_lock",
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

# A login made through Sign Up waits for an approver before it can be used.
on_login = ["techpark.registration.check_approval", "techpark.login.on_login"]

# Keep the TP Customer Contacts / Plants / Production / Commercial / Technical / Visits tabs in step with the real records
_customer_tab_sync = {
	"on_update": "techpark.customer_sync.on_record_change",
	"after_delete": "techpark.customer_sync.on_record_change",
}
doc_events = {
	# Sign Up: no set-password email yet, and a TP Registration for the approvers.
	"User": {
		"before_insert": "techpark.registration.on_user_before_insert",
		"after_insert": "techpark.registration.on_user_insert",
	},
	"Customer Contact": _customer_tab_sync,
	"Plant": _customer_tab_sync,
	"Customer Product Production": _customer_tab_sync,
	"Customer Turnover": _customer_tab_sync,
	"Customer Segment Application": _customer_tab_sync,
	"Wheel Specification": _customer_tab_sync,
	"Wheel Consumption": _customer_tab_sync,
	"Manufacturing Details": _customer_tab_sync,
	"Daily Visit Report": {
		**_customer_tab_sync,
		**_lock,
		"on_submit": "techpark.customer_sync.on_record_change",
		"on_cancel": "techpark.customer_sync.on_record_change",
		"on_update_after_submit": "techpark.customer_sync.on_record_change",
	},
}

# Scheduled Tasks
# ---------------

# Reminder digests: bell notification + email to each salesperson / manager.
scheduler_events = {
	"cron": {
		# Every day at 09:00: overdue follow-ups escalated to managers.
		"0 9 * * *": ["techpark.reminders.daily"],
		# Mondays at 09:00: cold prospects, customers not visited, pending actions by principal.
		"0 9 * * 1": ["techpark.reminders.weekly"],
		# 09:00 on the first day of every quarter: customer data still missing.
		"0 9 1 1,4,7,10 *": ["techpark.reminders.quarterly"],
	},
}

# scheduler_events = {
# 	"all": [
# 		"techpark.tasks.all"
# 	],
# 	"daily": [
# 		"techpark.tasks.daily"
# 	],
# 	"hourly": [
# 		"techpark.tasks.hourly"
# 	],
# 	"weekly": [
# 		"techpark.tasks.weekly"
# 	],
# 	"monthly": [
# 		"techpark.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "techpark.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "techpark.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "techpark.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "techpark.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["techpark.utils.before_request"]
# after_request = ["techpark.utils.after_request"]

# Job Events
# ----------
# before_job = ["techpark.utils.before_job"]
# after_job = ["techpark.utils.after_job"]

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
# 	"techpark.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
