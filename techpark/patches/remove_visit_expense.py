"""Expenses were taken out of TechPark (only DVR and Customer Master stay): delete the
expense charts and number cards, the Visit Expense DocType and its table with all records.
Migrate alone would leave the charts, cards and the table behind."""

import frappe

CHARTS = ["Monthly Visit Expenses", "Expenses by Type"]
CARDS = ["Expenses This Month", "Pending Expense Approvals"]


def execute():
	for chart in CHARTS:
		frappe.delete_doc("Dashboard Chart", chart, force=True, ignore_missing=True)
	for card in CARDS:
		frappe.delete_doc("Number Card", card, force=True, ignore_missing=True)

	frappe.delete_doc("DocType", "Visit Expense", force=True, ignore_missing=True)
	frappe.db.sql_ddl("drop table if exists `tabVisit Expense`")
