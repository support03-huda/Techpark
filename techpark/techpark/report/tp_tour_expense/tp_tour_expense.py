# Copyright (c) 2026, Techpark International
"""Tour Expense statement, in the client's format (Abhijit's tour expense sheet): the bills of the period
grouped by expense head (Food Exp., Lodging, Fuel, Local Conveyance, Fares, Misc.), each with its date,
description, short description (the customer / place) and amount, a total per head, and at the end the
head-wise summary with the grand total."""

import frappe
from frappe import _
from frappe.utils import flt

from techpark.techpark.doctype.tp_expense.tp_expense import expense_report_conditions


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_columns():
	return [
		# Data, not Int: header and total rows have no number.
		{"fieldname": "sr", "label": _("Sr. No."), "fieldtype": "Data", "width": 70},
		{"fieldname": "expense_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "expense_head", "label": _("Exp Head"), "fieldtype": "Data", "width": 160},
		{"fieldname": "description", "label": _("Description"), "fieldtype": "Data", "width": 300},
		{"fieldname": "short_description", "label": _("Short Description"), "fieldtype": "Data", "width": 200},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "passed_amount", "label": _("Passed Amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "employee_name", "label": _("Employee"), "fieldtype": "Data", "width": 150},
		{"fieldname": "expense", "label": _("Expense"), "fieldtype": "Link", "options": "TP Expense", "width": 140},
	]


def get_rows(filters):
	where, values = expense_report_conditions(filters)
	bills = frappe.db.sql(
		f"""
		select e.name as expense, e.employee_name, i.expense_date, i.expense_type as expense_head,
			i.description, i.customer_name, i.bill_no, i.amount, i.passed_amount
		from `tabTP Expense` e
		join `tabTP Expense Item` i on i.parent = e.name and i.parenttype = 'TP Expense'
		where {where}
		order by i.expense_type, i.expense_date, e.name, i.idx
		""",
		values,
		as_dict=True,
	)
	if not bills:
		return []

	heads = {}
	for b in bills:
		heads.setdefault(b.expense_head or _("Not set"), []).append(b)

	rows, summary = [], []
	for head, items in heads.items():
		rows.append({"expense_head": head, "is_head": 1, "indent": 0})
		for n, b in enumerate(items, 1):
			short = b.customer_name or ""
			if b.bill_no:
				short = f"{short} · {_('Bill')} {b.bill_no}" if short else f"{_('Bill')} {b.bill_no}"
			rows.append(
				{
					"sr": str(n),
					"expense_date": b.expense_date,
					"expense_head": head,
					"description": b.description,
					"short_description": short,
					"amount": b.amount,
					"passed_amount": b.passed_amount,
					"employee_name": b.employee_name,
					"expense": b.expense,
					"indent": 1,
				}
			)
		amount = sum(flt(b.amount) for b in items)
		passed = sum(flt(b.passed_amount) for b in items)
		rows.append(
			{"description": _("Total {0}").format(head), "amount": amount, "passed_amount": passed, "is_total": 1, "indent": 1}
		)
		summary.append((head, amount, passed))

	# Head-wise summary, like the bottom of the client's sheet
	rows.append({})
	rows.append({"expense_head": _("Summary"), "is_head": 1, "indent": 0})
	for head, amount, passed in summary:
		rows.append({"description": head, "amount": amount, "passed_amount": passed, "indent": 1})
	rows.append(
		{
			"description": _("Grand Total"),
			"amount": sum(s[1] for s in summary),
			"passed_amount": sum(s[2] for s in summary),
			"is_total": 1,
			"is_grand_total": 1,
			"indent": 1,
		}
	)
	return rows
