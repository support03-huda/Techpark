"""Expense module: the usual expense types, and a TP Team Member row for every active salesperson so
only Reports To has to be filled in. Leaves sites that already have them alone."""

import frappe

EXPENSE_TYPES = [
	"Travel / Fares",
	"Local Conveyance",
	"Fuel",
	"Toll / Parking",
	"Food",
	"Lodging & Boarding",
	"Daily Allowance",
	"Courier",
	"Postage & Telephone",
	"Business Promotion",
	"Gifts",
	"Miscellaneous",
]


def execute():
	if not frappe.db.count("TP Expense Type"):
		for expense_type in EXPENSE_TYPES:
			frappe.get_doc({"doctype": "TP Expense Type", "expense_type": expense_type}).insert(ignore_permissions=True)

	sales_users = frappe.get_all("Has Role", filters={"role": "Sales User", "parenttype": "User"}, pluck="parent")
	for user in frappe.get_all("User", filters={"name": ["in", sales_users or [""]], "enabled": 1}, pluck="name"):
		if user != "Administrator" and not frappe.db.exists("TP Team Member", user):
			frappe.get_doc({"doctype": "TP Team Member", "user": user}).insert(ignore_permissions=True)
