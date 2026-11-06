# Copyright (c) 2026, Techpark International
"""Data of the TechPark Dashboard (Frappe UI app at /tp, frontend/).

One call returns everything the page shows. Counts follow the same rules as the workspace
number cards (techpark/dashboard.py): get_list applies the record permissions, so a salesperson
sees their own visits, customers and expenses, managers the whole team.
"""

import frappe
from frappe.utils import add_days, add_months, flt, formatdate, get_first_day, getdate, today

from techpark.dashboard import PROSPECT_STALE_DAYS, _scope, _stale_prospects
from techpark.permission import has_app_permission

# Opportunity statuses in pipeline order (the client's development cycle).
PIPELINE = [
	"Introduction",
	"Enquiry Received",
	"Sent to Principal",
	"Offer Received",
	"Offer Submitted",
	"Trial PO Received",
	"Sample Received",
	"Trial in Progress",
	"Successful Trial",
	"Bulk Trial PO",
	"Regularization",
]
EXPENSE_PENDING = ("Pending Manager", "Pending Admin")
MONTHS = 12


@frappe.whitelist()
def get_dashboard():
	if not has_app_permission():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	user, team, now = _scope()
	month_start = get_first_day(now)
	since = add_months(month_start, -(MONTHS - 1))

	visits = frappe.get_list(
		"Daily Visit Report",
		filters={"docstatus": 1, "visit_date": (">=", since)},
		fields=[
			"name", "visit_date", "customer", "customer_name", "employee_name", "visit_purpose",
			"dvr_stage", "dvr_type", "lead_status", "lead_stage",
		],
		order_by="visit_date desc, creation desc",
		limit_page_length=0,
	)
	follow_ups = _follow_ups(user, team, now)

	return {
		"user": {"name": frappe.utils.get_fullname(user), "is_manager": team},
		"today": str(now),
		"follow_ups": {
			"overdue": sum(1 for f in follow_ups if f.due and f.due < now),
			"today": sum(1 for f in follow_ups if f.due == now),
			"week": sum(1 for f in follow_ups if f.due and now <= f.due <= add_days(now, 7)),
			"stale_prospects": _stale_prospects(user, team, now),
			"stale_days": PROSPECT_STALE_DAYS,
			"list": [
				{
					"todo": f.name, "visit": f.reference_name, "customer": f.customer_name,
					"note": f.description, "date": str(f.due) if f.due else None, "owner": f.owner_name,
				}
				for f in follow_ups[:8]
			],
		},
		"visits": {
			"this_month": sum(1 for v in visits if getdate(v.visit_date) >= month_start),
			"last_month": sum(1 for v in visits if add_months(month_start, -1) <= getdate(v.visit_date) < month_start),
			"monthly": _monthly(visits, since, lambda v: 1, "visit_date"),
			"by_stage": _group(visits, "dvr_stage"),
			"by_purpose": _group(visits, "visit_purpose"),
			"by_type": _group(visits, "dvr_type"),
			"by_principal": _by_principal(visits),
			"recent": [
				{
					"name": v.name, "date": str(v.visit_date), "customer": v.customer_name, "by": v.employee_name,
					"stage": v.dvr_stage, "purpose": v.visit_purpose, "status": v.lead_status,
				}
				for v in visits[:8]
			],
		},
		"pipeline": _pipeline(),
		"customers": _customers(),
		"expenses": _expenses(month_start, since),
	}


def _follow_ups(user, team, now):
	"""Open follow-ups of submitted visits, earliest due first."""
	filters = {"reference_type": "Daily Visit Report", "status": "Open"}
	if not team:
		filters["allocated_to"] = user
	todos = frappe.get_all(
		"ToDo", filters=filters, fields=["name", "date", "reference_name", "description", "allocated_to"], limit=500
	)
	visits = {
		v.name: v
		for v in frappe.get_all(
			"Daily Visit Report",
			filters={"name": ("in", [t.reference_name for t in todos] or [""]), "docstatus": 1},
			fields=["name", "customer_name"],
		)
	}
	out = []
	for t in todos:
		if t.reference_name not in visits:
			continue  # visit cancelled
		t.due = getdate(t.date) if t.date else None
		t.customer_name = visits[t.reference_name].customer_name
		t.description = frappe.utils.strip_html(t.description or "")[:140]
		t.owner_name = frappe.utils.get_fullname(t.allocated_to) if t.allocated_to else ""
		out.append(t)
	out.sort(key=lambda t: (t.due is None, t.due or now))
	return out


def _monthly(rows, since, value, date_field):
	"""[{month: "Nov 25", value}] for the last MONTHS months, oldest first."""
	months = [add_months(since, i) for i in range(MONTHS)]
	totals = {(m.year, m.month): 0 for m in months}
	for r in rows:
		d = getdate(r.get(date_field))
		if (d.year, d.month) in totals:
			totals[(d.year, d.month)] += value(r)
	return [{"month": formatdate(m, "MMM yy"), "value": flt(totals[(m.year, m.month)], 2)} for m in months]


def _group(rows, field, empty="Not set"):
	counts = {}
	for r in rows:
		key = r.get(field) or empty
		counts[key] = counts.get(key, 0) + 1
	return [{"label": k, "value": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


def _by_principal(visits):
	rows = frappe.get_all(
		"DVR Principal",
		filters={"parenttype": "Daily Visit Report", "parent": ("in", [v.name for v in visits] or [""])},
		fields=["principal"],
	)
	return _group(rows, "principal")[:10]


def _pipeline():
	"""Principal-wise leads at their latest stage (rows of the Application Development Status report)."""
	from techpark.techpark.report.application_development_status.application_development_status import get_data

	rows = get_data(frappe._dict())
	counts = {stage: 0 for stage in PIPELINE}
	for r in rows:
		if r.get("lead_stage") in counts:
			counts[r["lead_stage"]] += 1
	return {
		"stages": [{"stage": s, "value": counts[s]} for s in PIPELINE],
		"trials": counts["Trial PO Received"] + counts["Sample Received"] + counts["Trial in Progress"],
		"successful": counts["Successful Trial"],
		"won": counts["Bulk Trial PO"],
		"regularization": counts["Regularization"],
	}


def _customers():
	customers = frappe.get_list(
		"TP Customer", fields=["customer_status", "territory_region"], limit_page_length=0
	)
	return {
		"total": len(customers),
		"active": sum(1 for c in customers if c.customer_status == "Active Customer"),
		"prospects": sum(1 for c in customers if c.customer_status == "Prospect"),
		"by_status": _group(customers, "customer_status"),
		"by_region": _group(customers, "territory_region"),
	}


def _expenses(month_start, since):
	expenses = frappe.get_list(
		"TP Expense",
		filters={"entry_date": (">=", since)},
		fields=["entry_date", "employee_name", "status", "total_amount", "passed_amount"],
		limit_page_length=0,
	)
	this_month = [e for e in expenses if getdate(e.entry_date) >= month_start]
	pending = frappe.get_list("TP Expense", filters={"status": ("in", EXPENSE_PENDING)}, fields=["total_amount"])
	by_employee = {}
	for e in this_month:
		by_employee[e.employee_name or "?"] = by_employee.get(e.employee_name or "?", 0) + flt(e.total_amount)
	return {
		"this_month": flt(sum(flt(e.total_amount) for e in this_month), 2),
		"approved_this_month": flt(sum(flt(e.passed_amount) for e in this_month if e.status == "Approved"), 2),
		"pending_count": len(pending),
		"pending_amount": flt(sum(flt(p.total_amount) for p in pending), 2),
		"monthly": _monthly(expenses, since, lambda e: flt(e.total_amount), "entry_date"),
		"by_employee": [
			{"label": k, "value": flt(v, 2)} for k, v in sorted(by_employee.items(), key=lambda kv: -kv[1])
		],
	}
