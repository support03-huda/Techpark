"""The "TechPark Today" Custom HTML Block is no longer used: the workspace is built from Frappe's own widgets."""

import frappe


def execute():
	if frappe.db.exists("Custom HTML Block", "TechPark Today"):
		frappe.delete_doc("Custom HTML Block", "TechPark Today", ignore_permissions=True, force=True)
