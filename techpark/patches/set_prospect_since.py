"""Backfill "Prospect Since" for customers that were already Prospects before the field existed,
so the "Customer Prospect Over 7 Days" notification can count from their creation date."""

import frappe
from frappe.utils import getdate


def execute():
	for c in frappe.get_all(
		"TP Customer",
		filters={"customer_status": "Prospect", "prospect_since": ("is", "not set")},
		fields=["name", "creation"],
	):
		frappe.db.set_value("TP Customer", c.name, "prospect_since", getdate(c.creation), update_modified=False)
