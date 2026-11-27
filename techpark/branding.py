# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""2026-11-26: the logo and app icon are set in TechPark Settings > Branding (client: nothing hard coded).
The files shipped with the app are only what a new site starts with (patches/branding_settings.py)."""

import frappe

SHIPPED_LOGO = "/assets/techpark/images/techpark_logo.png"
SHIPPED_ICON = "/assets/techpark/images/techpark_icon.png"


def _setting(field):
	if not frappe.get_meta("TechPark Settings").has_field(field):  # before migrate
		return None
	return frappe.db.get_single_value("TechPark Settings", field)


def company_logo():
	"""For print formats (jinja) and the login page."""
	return _setting("company_logo") or SHIPPED_LOGO


def app_icon_url():
	return _setting("app_icon") or SHIPPED_ICON


@frappe.whitelist(allow_guest=True)
def app_icon():
	"""The apps screen asks this URL (hooks.py): it redirects to the icon set in TechPark Settings."""
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = app_icon_url()


def apply_branding():
	"""TechPark Settings saved / every migrate: logo on the login page, icon on the desk home."""
	logo, icon = company_logo(), app_icon_url()
	if frappe.db.get_single_value("Website Settings", "app_logo") != logo:
		frappe.db.set_single_value("Website Settings", "app_logo", logo)
	if frappe.db.exists("Desktop Icon", "TechPark") and frappe.db.get_value("Desktop Icon", "TechPark", "logo_url") != icon:
		frappe.db.set_value("Desktop Icon", "TechPark", "logo_url", icon)
		frappe.cache.delete_key("desktop_icons")
	frappe.clear_cache()
