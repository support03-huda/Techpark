"""Rename TechPark's "Customer" DocType to "TP Customer".

ERPNext ships its own "Customer" DocType; on a site with both apps, whichever
syncs last wins. Sites where "Customer" is still TechPark's keep their data
by renaming it in place (table and every Link pointing to it). Where ERPNext
already owns "Customer" this does nothing and "TP Customer" is created fresh.
"""

import frappe


def execute():
	if frappe.db.exists("DocType", "TP Customer"):
		return
	if frappe.db.get_value("DocType", "Customer", "module") != "TechPark":
		return
	frappe.rename_doc("DocType", "Customer", "TP Customer", force=True)
