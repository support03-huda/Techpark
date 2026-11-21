# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: client wants Industry Domain (Customer only) and Industry/Product Segment (everywhere else)
"""Customer's Industry Domain is its own master again: create one for every value customers already have."""

import frappe


def execute():
	for value in frappe.get_all("TP Customer", filters={"industry_domain": ("is", "set")}, pluck="industry_domain", distinct=True):
		value = (value or "").strip()
		if value and not frappe.db.exists("Industry Domain", value):
			frappe.get_doc({"doctype": "Industry Domain", "industry_name": value}).insert(ignore_permissions=True)
