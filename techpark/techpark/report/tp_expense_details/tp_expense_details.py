# Copyright (c) 2026, Techpark International
"""Expense Details report: one row per bill, with the expense it belongs to and its Tally account."""

import frappe
from frappe import _

from techpark.techpark.doctype.tp_expense.tp_expense import expense_report_conditions


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_columns():
	return [
		{"fieldname": "expense", "label": _("Expense"), "fieldtype": "Link", "options": "TP Expense", "width": 150},
		{"fieldname": "entry_date", "label": _("Entry Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "visit", "label": _("Visit (DVR)"), "fieldtype": "Link", "options": "Daily Visit Report", "width": 130},
		# Data, not Int: the total row must not add up the row numbers.
		{"fieldname": "idx", "label": _("Sr"), "fieldtype": "Data", "width": 50},
		{"fieldname": "expense_date", "label": _("Expense Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "expense_type", "label": _("Expense Type"), "fieldtype": "Link", "options": "TP Expense Type", "width": 160},
		{"fieldname": "tally_account", "label": _("Tally Account"), "fieldtype": "Data", "width": 200},
		{"fieldname": "bill_no", "label": _("Bill No"), "fieldtype": "Data", "width": 100},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Data", "width": 180},
		{"fieldname": "description", "label": _("Detail Description"), "fieldtype": "Data", "width": 220},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "passed_amount", "label": _("Passed Amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "bill", "label": _("Bill"), "fieldtype": "Attach", "width": 120},
		{"fieldname": "other_attachment", "label": _("Other Attachment"), "fieldtype": "Attach", "width": 140},
	]


def get_rows(filters):
	where, values = expense_report_conditions(filters)
	if filters.expense_type:
		where += " and i.expense_type = %(expense_type)s"
		values["expense_type"] = filters.expense_type
	return frappe.db.sql(
		f"""
		select e.name as expense, e.entry_date, e.employee_name, e.status, i.visit,
			i.idx, i.expense_date, i.expense_type, t.tally_account, i.bill_no, i.customer_name as customer, i.description,
			i.amount, i.passed_amount, i.bill, i.other_attachment
		from `tabTP Expense` e
		join `tabTP Expense Item` i on i.parent = e.name and i.parenttype = 'TP Expense'
		left join `tabTP Expense Type` t on t.name = i.expense_type
		where {where}
		order by e.entry_date, e.name, i.idx
		""",
		values,
		as_dict=True,
	)
