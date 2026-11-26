# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: a customer's Technical Leads tab held the same lead several times (one lead 14 times): rebuild those tabs
"""Rebuild the Technical Leads tab of every customer whose tab has a lead twice (from the leads themselves)."""

import frappe

from techpark.customer_sync import pull_from_records


def execute():
	customers = frappe.db.sql_list(
		"""select parent from `tabTP Customer Technical Lead`
		where parenttype = 'TP Customer' and ifnull(record, '') != ''
		group by parent, record having count(*) > 1"""
	)
	for customer in set(customers):
		pull_from_records(customer, ["technical_leads"])
