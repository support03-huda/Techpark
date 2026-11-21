# Last edited: 2026-11-13
# Copyright (c) 2026, Techpark International
"""Industry Segment -> Product -> Application: a product takes the industry segment of the
applications already made with it."""

import frappe


def execute():
	for product, industry in frappe.get_all(
		"Customer Application",
		filters={"product": ("is", "set"), "industry_domain": ("is", "set")},
		fields=["product", "industry_domain"],
		as_list=True,
	):
		if not frappe.db.get_value("Customer Product", product, "industry_domain"):
			frappe.db.set_value("Customer Product", product, "industry_domain", industry, update_modified=False)
