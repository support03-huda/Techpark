# Copyright (c) 2026, Techpark International
"""Technical Leads show their line's Stage / Current Status: fill them from the existing opportunities."""

import frappe

from techpark.opportunity import refresh_opportunity


def execute():
	for name in frappe.get_all("TP Opportunity", pluck="name"):
		refresh_opportunity(name)
