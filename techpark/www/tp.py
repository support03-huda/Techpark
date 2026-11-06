# Copyright (c) 2026, Techpark International
"""TechPark Dashboard: the Frappe UI app at /tp (built from frontend/ into tp.html)."""

import frappe
from frappe import _

from techpark.permission import has_app_permission

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/tp"
		raise frappe.Redirect
	if not has_app_permission():
		frappe.throw(_("You do not have permission to open the TechPark Dashboard"), frappe.PermissionError)
	context.boot = {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"site_name": frappe.local.site,
		"user": frappe.session.user,
	}
	return context
