"""TechPark logo on the login page (and desk) from the app, not an uploaded file.
Its size comes from public/css/techpark_web.css, so the CSS first put in Website Settings
Head HTML is removed."""

import frappe

LOGO = "/assets/techpark/images/techpark_logo.png"
HEAD_CSS_MARKER = "TechPark logo on the login page"


def execute():
	settings = frappe.get_single("Website Settings")
	settings.app_logo = LOGO
	if HEAD_CSS_MARKER in (settings.head_html or ""):
		settings.head_html = ""
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)
	frappe.clear_cache()
