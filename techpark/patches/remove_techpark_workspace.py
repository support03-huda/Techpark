# Last edited: 2026-11-07
# Copyright (c) 2026, Techpark International
"""Delete the old TechPark workspace (/desk/techpark, the Overview page with tabs); users land on the Dashboard page."""

import frappe


def execute():
	frappe.db.sql("update `tabUser` set default_workspace = null where default_workspace = 'TechPark'")
	if frappe.db.exists("Workspace", "TechPark"):
		frappe.delete_doc("Workspace", "TechPark", force=True, ignore_permissions=True)
	frappe.cache.delete_value("home_page")
	frappe.clear_cache()
