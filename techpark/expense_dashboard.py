# Copyright (c) 2026, Techpark International
"""Figures of the Expense Dashboard page: totals per status, 12-month trend, amount per expense type,
employee and customer, and the expenses waiting for approval with how long they have waited.
Everybody sees only the expenses they may see (own, team, or all for approvers)."""

import frappe
from frappe import _
from frappe.utils import add_months, cint, date_diff, flt, get_first_day, getdate, now_datetime

from techpark.permission import get_visible_users, sql_list
from techpark.techpark.doctype.tp_expense.tp_expense import expense_report_conditions

TREND_MONTHS = 12
# Rows in a "top" list.
TOP = 10
PENDING_STATUSES = ("Pending Manager", "Pending Admin")


# Everything the Expense Dashboard page shows for one period.
@frappe.whitelist()
def get_dashboard(from_date, to_date, employee=None):
	filters = frappe._dict(from_date=from_date, to_date=to_date, employee=employee)
	where, values = expense_report_conditions(filters)
	return {
		"tiles": get_tiles(where, values),
		"trend": get_trend(filters),
		"by_type": get_by_type(where, values),
		"by_employee": get_by_employee(where, values),
		"by_customer": get_by_customer(where, values),
		"pending": get_pending(employee),
	}


# Counts and amounts per status in the period.
def get_tiles(where, values):
	return frappe.db.sql(
		f"""
		select count(*) as claims,
			ifnull(sum(e.total_amount), 0) as claimed,
			sum(e.status = 'Approved') as approved_count,
			ifnull(sum(case when e.status = 'Approved' then e.passed_amount end), 0) as approved,
			ifnull(sum(case when e.status = 'Approved' then e.total_amount - e.passed_amount end), 0) as cut,
			sum(e.status = 'Pending Manager') as manager_count,
			ifnull(sum(case when e.status = 'Pending Manager' then e.total_amount end), 0) as manager_amount,
			sum(e.status = 'Pending Admin') as admin_count,
			ifnull(sum(case when e.status = 'Pending Admin' then e.total_amount end), 0) as admin_amount,
			sum(e.status = 'Draft') as draft_count,
			sum(e.status = 'Draft' and ifnull(e.rejection_reason, '') != '') as returned_count
		from `tabTP Expense` e
		where {where}
		""",
		values,
		as_dict=True,
	)[0]


# Claimed and approved amount per month, for the 12 months that end with the month of the To date.
def get_trend(filters):
	last_month = get_first_day(filters.to_date)
	first_month = add_months(last_month, -(TREND_MONTHS - 1))
	where, values = expense_report_conditions(frappe._dict(filters, from_date=first_month, to_date=filters.to_date))
	rows = frappe.db.sql(
		f"""
		select date_format(e.entry_date, '%%Y-%%m') as month,
			sum(e.total_amount) as claimed,
			sum(case when e.status = 'Approved' then e.passed_amount else 0 end) as approved
		from `tabTP Expense` e
		where {where}
		group by month
		""",
		values,
		as_dict=True,
	)
	by_month = {row.month: row for row in rows}
	months = [add_months(first_month, offset) for offset in range(TREND_MONTHS)]
	return {
		"labels": [getdate(month).strftime("%b %y") for month in months],
		"claimed": [flt((by_month.get(getdate(month).strftime("%Y-%m")) or {}).get("claimed")) for month in months],
		"approved": [flt((by_month.get(getdate(month).strftime("%Y-%m")) or {}).get("approved")) for month in months],
	}


# Amount and number of bills per expense type, the largest first.
def get_by_type(where, values):
	return frappe.db.sql(
		f"""
		select i.expense_type as label, sum(i.amount) as amount, count(*) as bills
		from `tabTP Expense` e
		join `tabTP Expense Item` i on i.parent = e.name and i.parenttype = 'TP Expense'
		where {where}
		group by i.expense_type
		order by amount desc
		limit {TOP}
		""",
		values,
		as_dict=True,
	)


# Amount and number of claims per employee, the largest first.
def get_by_employee(where, values):
	return frappe.db.sql(
		f"""
		select e.employee_name as label, sum(e.total_amount) as amount, count(*) as claims
		from `tabTP Expense` e
		where {where}
		group by e.employee
		order by amount desc
		limit {TOP}
		""",
		values,
		as_dict=True,
	)


# Amount and number of bills per customer, the largest first; bills without a customer are left out.
def get_by_customer(where, values):
	return frappe.db.sql(
		f"""
		select i.customer_name as label, sum(i.amount) as amount, count(*) as bills
		from `tabTP Expense` e
		join `tabTP Expense Item` i on i.parent = e.name and i.parenttype = 'TP Expense'
		where {where} and ifnull(i.customer_name, '') != ''
		group by i.customer_name
		order by amount desc
		limit {TOP}
		""",
		values,
		as_dict=True,
	)


# Every expense that waits for approval now, whatever its date, the one waiting longest first.
def get_pending(employee=None):
	conditions = ["e.status in %(statuses)s"]
	values = {"statuses": PENDING_STATUSES}
	if employee:
		conditions.append("e.employee = %(employee)s")
		values["employee"] = employee
	team = get_visible_users()
	if team is not None:
		conditions.append(f"e.employee in {sql_list(team)}")
	rows = frappe.db.sql(
		f"""
		select e.name, e.employee_name, e.status, e.total_amount, e.entry_date, e.sent_on, e.approved_on,
			m.full_name as manager_name
		from `tabTP Expense` e
		left join `tabTP Team Member` tm on tm.user = e.employee and tm.inactive = 0
		left join `tabUser` m on m.name = tm.reports_to
		where {" and ".join(conditions)}
		""",
		values,
		as_dict=True,
	)
	now = now_datetime()
	for row in rows:
		since = (row.approved_on or row.sent_on) if row.status == "Pending Admin" else row.sent_on
		since = since or row.entry_date
		row.days = max(cint(date_diff(now, since)), 0)
		row.waiting_for = _("Approver") if row.status == "Pending Admin" else (row.manager_name or _("Manager"))
	return sorted(rows, key=lambda row: -row.days)
