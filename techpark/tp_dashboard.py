# Copyright (c) 2026, Techpark International
"""Data of the TechPark Dashboard page (techpark-dashboard) and the Development Board page
(techpark-development-board).

One call returns everything a page shows. Counts follow the same rules as the workspace
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
	"Enquiry Follow-up",
	"Order Follow-up",
	"Delivery Follow-up",
	"Payment Follow-up",
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
			"stages": _visits_by_stage(visits, since, month_start),
		},
		"pipeline": _pipeline(),
		"opportunities": _opportunities(now, visits, month_start),
		"customers": _customers(),
		"expenses": _expenses(month_start, since),
	}


def _visits_by_stage(visits, since, month_start):
	"""Visits tab, one part per stage: the visits with a principal row in that stage (a visit with both
	stages counts in both), their rows' statuses, principals, people and the latest visits."""
	from techpark.techpark.doctype.daily_visit_report.daily_visit_report import DEVELOPMENT_PROGRESS, SALES_PROGRESS

	rows = frappe.get_all(
		"DVR Principal",
		filters={"parenttype": "Daily Visit Report", "parent": ("in", [v.name for v in visits] or [""])},
		fields=["parent", "stage", "development_status", "sales_status", "principal", "application", "opportunity"],
	)
	last_month_start = add_months(month_start, -1)
	out = {}
	for stage, statuses in (("Development", DEVELOPMENT_PROGRESS), ("Sales", SALES_PROGRESS)):
		stage_rows = [r for r in rows if r.stage == stage]
		for r in stage_rows:
			r.status = (r.sales_status if stage == "Sales" else r.development_status) or "Not set"
		parents = {r.parent for r in stage_rows}
		stage_visits = [v for v in visits if v.name in parents]
		this_month = [v for v in stage_visits if getdate(v.visit_date) >= month_start]
		month_names = {v.name for v in this_month}
		counts = {}
		for r in stage_rows:
			counts[r.status] = counts.get(r.status, 0) + 1
		lines_by_visit = {}
		for r in stage_rows:
			lines_by_visit.setdefault(r.parent, []).append(
				{"application": r.application, "principal": r.principal, "status": r.status}
			)
		out[stage] = {
			"total": len(stage_visits),
			"this_month": len(this_month),
			"last_month": sum(1 for v in stage_visits if last_month_start <= getdate(v.visit_date) < month_start),
			"customers_this_month": len({v.customer for v in this_month}),
			"lines_this_month": len({r.opportunity or (r.parent, r.application, r.principal) for r in stage_rows if r.parent in month_names}),
			"monthly": _monthly(stage_visits, since, lambda v: 1, "visit_date"),
			# In the order of the cycle, then anything else
			"by_status": [{"label": s, "value": counts[s]} for s in statuses if counts.get(s)]
			+ [{"label": s, "value": n} for s, n in counts.items() if s not in statuses],
			"by_principal": _group(stage_rows, "principal")[:10],
			"by_person": _group(stage_visits, "employee_name")[:10],
			"by_type": _group(stage_visits, "dvr_type"),
			"recent": [
				{
					"name": v.name, "date": str(v.visit_date), "customer": v.customer_name, "by": v.employee_name,
					"purpose": v.visit_purpose, "lines": lines_by_visit.get(v.name, []),
				}
				for v in stage_visits[:10]
			],
		}
	return out


OPPORTUNITY_FIELDS = [
	"name", "customer", "customer_name", "application", "principal", "supplier_product_category", "category_name", "spec", "size",
	"importance", "sales_person", "stage", "status", "progress", "lead_status", "next_action",
	"next_action_date", "last_visit", "visits", "remarks", "invoice_oc", "samples", "trials", "bulk_trial_po", "regularised",
]
IMPORTANCE_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _opportunities(now, visits, month_start):
	"""Application lines: totals, the High-importance open ones and a sales-person table."""
	opps = frappe.get_list(
		"TP Opportunity", filters={"visits": (">", 0)}, fields=OPPORTUNITY_FIELDS, limit_page_length=0
	)
	open_ = [o for o in opps if o.lead_status in ("Open", "On Hold")]
	overdue = lambda o: o.next_action_date and getdate(o.next_action_date) < now
	visits_this_month = {}
	for v in visits:
		if getdate(v.visit_date) >= month_start:
			visits_this_month[v.employee_name] = visits_this_month.get(v.employee_name, 0) + 1

	people = {}
	for o in opps:
		name = frappe.utils.get_fullname(o.sales_person) if o.sales_person else "Not set"
		p = people.setdefault(name, {"name": name, "open": 0, "development": 0, "sales": 0, "won": 0, "lost": 0, "overdue": 0})
		if o.lead_status in ("Open", "On Hold"):
			p["open"] += 1
			p["development" if o.stage == "Development" else "sales"] += 1
			p["overdue"] += 1 if overdue(o) else 0
		elif o.lead_status == "Won":
			p["won"] += 1
		elif o.lead_status == "Lost":
			p["lost"] += 1
	for p in people.values():
		p["visits"] = visits_this_month.get(p["name"], 0)

	hot = sorted(
		(o for o in open_ if o.importance == "High"),
		key=lambda o: (o.next_action_date is None, str(o.next_action_date or "")),
	)
	return {
		"total": len(opps),
		"open": len(open_),
		"development": sum(1 for o in open_ if o.stage == "Development"),
		"sales": sum(1 for o in open_ if o.stage == "Sales"),
		"won": sum(1 for o in opps if o.lead_status == "Won"),
		"lost": sum(1 for o in opps if o.lead_status == "Lost"),
		"high": sum(1 for o in open_ if o.importance == "High"),
		"overdue": sum(1 for o in open_ if overdue(o)),
		"hot": [_line(o) for o in hot[:8]],
		"by_person": sorted(people.values(), key=lambda p: -p["open"]),
	}


def _line(o):
	return {
		"name": o.name, "customer": o.customer_name, "application": o.application, "principal": o.principal,
		"spec": o.spec, "status": o.status, "stage": o.stage, "progress": o.progress,
		"next_action": o.next_action, "date": str(o.next_action_date) if o.next_action_date else None,
	}


@frappe.whitelist()
def get_development_board(customer=None, principal=None, sales_person=None, importance=None, show="Open"):
	"""Development Board: every application line (opportunity) with its customer, grouped on the page."""
	if not has_app_permission():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	from techpark.techpark.doctype.daily_visit_report.daily_visit_report import (
		DEVELOPMENT_PROGRESS,
		SALES_PROGRESS,
	)

	filters = {"visits": (">", 0)}
	for field, value in (("customer", customer), ("principal", principal), ("sales_person", sales_person), ("importance", importance)):
		if value:
			filters[field] = value
	if show == "Open":
		filters["lead_status"] = ("in", ("Open", "On Hold"))
	elif show in ("Won", "Lost"):
		filters["lead_status"] = show
	opps = frappe.get_list("TP Opportunity", filters=filters, fields=OPPORTUNITY_FIELDS, limit_page_length=0)

	customers = {
		c.name: c
		for c in frappe.get_all(
			"TP Customer",
			filters={"name": ("in", list({o.customer for o in opps}) or [""])},
			fields=["name", "territory_region", "industry_domain", "customer_status"],
		)
	}
	rows = []
	for o in opps:
		c = customers.get(o.customer) or frappe._dict()
		rows.append(
			{
				**o,
				"region": c.territory_region,
				"industry": c.industry_domain,
				"customer_status": c.customer_status,
				"sales_person_name": frappe.utils.get_fullname(o.sales_person) if o.sales_person else "",
				"next_action_date": str(o.next_action_date) if o.next_action_date else None,
				"last_visit": str(o.last_visit) if o.last_visit else None,
			}
		)
	rows.sort(key=lambda r: (IMPORTANCE_ORDER.get(r["importance"], 3), r["customer_name"] or "", r["application"] or ""))
	statuses = [{"status": s, "stage": "Development"} for s in DEVELOPMENT_PROGRESS] + [
		{"status": s, "stage": "Sales"} for s in SALES_PROGRESS
	]
	return {"rows": rows, "statuses": statuses, "today": today()}


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
		# Sales cycle follow-ups: lines waiting on an enquiry / order / delivery / payment
		"follow_ups": [{"status": s, "value": counts[s]} for s in ("Enquiry Follow-up", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up")],
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
