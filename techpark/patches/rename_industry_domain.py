# Copyright (c) 2026, Techpark International
"""The Industry Domain master is called Industry Segment everywhere (the client's term)."""

import frappe


def execute():
	if frappe.db.exists("DocType", "Industry Domain") and not frappe.db.exists("DocType", "Industry Segment"):
		frappe.rename_doc("DocType", "Industry Domain", "Industry Segment", force=True)
