# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
"""Data of the TechPark Dashboard page (techpark-dashboard) and the Development Board page
(techpark-development-board).

One call returns everything a page shows. Counts follow the same rules as the workspace
number cards (techpark/dashboard.py): get_list applies the record permissions, so a salesperson
sees their own visits, customers and expenses, managers the whole team.
"""

import frappe
from frappe.utils import add_days, add_months, flt, formatdate, get_first_day, getdate, today

from techpark.dashboard import _scope, _stale_prospects, stale_days
from techpark.masters import priority_order  # 2026-11-26
from techpark.permission import has_app_permission

# 2026-11-27: the funnel follows the Sort Order of the TP Development / Sales Status masters (was a fixed list)


def _pipeline_order():
	"""2026-11-27: funnel = active Development then Sales statuses in their Sort Order; lines that ended
	(Counts As Lost / On Hold) are not part of the funnel."""
	from techpark.statuses import status_rows

	return list(dict.fromkeys(r.name for r in status_rows() if r.is_active and r.result in ("Open", "Won")))


EXPENSE_PENDING = ("Pending Manager", "Pending Admin")
MONTHS = 12


@frappe.whitelist()
def get_dashboard(sales_person=None):
	if not has_app_permission():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	user, team, now = _scope()
	# 2026-11-23: an admin may look at one sales person's dashboard (Sales Person filter)
	can_filter = team
	sp = sales_person if (team and sales_person) else None
	if sp:
		user, team = sp, False
	month_start = get_first_day(now)
	since = add_months(month_start, -(MONTHS - 1))

	visits = frappe.get_list(
		"Daily Visit Report",
		filters={"docstatus": 1, "visit_date": (">=", since), **({"visited_by": sp} if sp else {})},
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
		# 2026-11-23: Sales Person filter for admins
		"can_filter": can_filter,
		"sales_person": sp,
		"people": _sales_people() if can_filter else [],
		"today": str(now),
		"follow_ups": {
			"overdue": sum(1 for f in follow_ups if f.due and f.due < now),
			"today": sum(1 for f in follow_ups if f.due == now),
			"week": sum(1 for f in follow_ups if f.due and now <= f.due <= add_days(now, 7)),
			"stale_prospects": _stale_prospects(user, team, now),
			"stale_days": stale_days(),
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
		"pipeline": _pipeline(sp),
		"opportunities": _opportunities(now, visits, month_start, sp),
		"customers": _customers(sp),
		"expenses": _expenses(month_start, since, sp),
	}


def _visits_by_stage(visits, since, month_start):
	"""Visits tab, one part per stage: the visits with a principal row in that stage (a visit with both
	stages counts in both), their rows' statuses, principals, people and the latest visits."""
	from techpark.statuses import stage_statuses  # 2026-11-26: statuses are masters now

	DEVELOPMENT_PROGRESS, SALES_PROGRESS = stage_statuses("Development"), stage_statuses("Sales")
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
	"next_action_date", "last_visit", "visits", "remarks", "present_status", "joint_with", "invoice_oc", "samples", "trials", "bulk_trial_po", "regularised",
]
# 2026-11-26: importance order = Sort Order of the TP Priority master


def _opportunities(now, visits, month_start, sp=None):
	"""Application lines: totals, the High-importance open ones and a sales-person table."""
	opps = frappe.get_list(
		"TP Opportunity", filters={"visits": (">", 0), **({"sales_person": sp} if sp else {})}, fields=OPPORTUNITY_FIELDS, limit_page_length=0
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
def get_development_board(customer=None, principal=None, sales_person=None, importance=None, show="Open", stage=None):
	"""Development / Sales Board: every application line (opportunity) of that stage with its customer."""
	if not has_app_permission():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	from techpark.statuses import stage_statuses  # 2026-11-26: board columns = the active statuses of the masters

	DEVELOPMENT_PROGRESS, SALES_PROGRESS = stage_statuses("Development"), stage_statuses("Sales")

	filters = {"visits": (">", 0)}
	for field, value in (("customer", customer), ("principal", principal), ("sales_person", sales_person), ("importance", importance)):
		if value:
			filters[field] = value
	if stage in ("Development", "Sales"):
		filters["stage"] = stage
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
	order = priority_order()
	rows.sort(key=lambda r: (order.get(r["importance"], 9999), r["customer_name"] or "", r["application"] or ""))
	# 2026-11-26: Development board = every development status in its Sort Order (Successful Trial too: the line
	# stays here until the lead is Regularised); the Sales board starts at the successful trial.
	statuses = [{"status": s, "stage": "Development"} for s in DEVELOPMENT_PROGRESS]
	sales_statuses = [{"status": "Successful Trial", "stage": "Sales"}] + [{"status": s, "stage": "Sales"} for s in SALES_PROGRESS]
	if stage == "Sales":
		statuses = sales_statuses
	elif stage != "Development":
		statuses += sales_statuses
	return {"rows": rows, "statuses": statuses, "today": today()}


@frappe.whitelist()
def get_calendar(start, end):
	"""Dashboard calendar: visits (DVRs) and open follow-ups between two dates. Salespeople see their own."""
	if not has_app_permission():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	user, team, now = _scope()
	start, end = getdate(start), getdate(end)
	visits = frappe.get_list(
		"Daily Visit Report",
		filters={"visit_date": ("between", [start, end]), "docstatus": ("<", 2)},
		fields=["name", "visit_date", "customer_name", "dvr_stage", "application", "development_status", "sales_status",
		        "employee_name", "docstatus"],
		order_by="visit_date, visit_time",
		limit_page_length=1000,
	)
	todo_filters = {"reference_type": "Daily Visit Report", "status": "Open", "date": ("between", [start, end])}
	if not team:
		todo_filters["allocated_to"] = user
	todos = frappe.get_all("ToDo", filters=todo_filters, fields=["name", "date", "reference_name", "description", "allocated_to"], limit=1000)
	customers = {
		v.name: v.customer_name
		for v in frappe.get_all(
			"Daily Visit Report", filters={"name": ("in", [t.reference_name for t in todos] or [""])}, fields=["name", "customer_name"]
		)
	}
	pending = frappe.get_list(
		"TP Pending Work",
		filters={"status": ("in", ("Open", "In Progress")), "due_date": ("between", [start, end])},
		fields=["name", "task", "due_date", "customer_name", "responsible_names"],
		limit_page_length=1000,
	)
	return {
		"today": str(now),
		"pending": [
			{"name": p.name, "date": str(p.due_date), "task": p.task, "customer": p.customer_name, "by": p.responsible_names}
			for p in pending
		],
		"visits": [
			{
				"name": v.name, "date": str(v.visit_date), "customer": v.customer_name, "stage": v.dvr_stage,
				"application": v.application, "status": v.sales_status or v.development_status, "by": v.employee_name,
				"draft": v.docstatus == 0,
			}
			for v in visits
		],
		"follow_ups": [
			{
				"name": t.name, "date": str(t.date), "visit": t.reference_name, "customer": customers.get(t.reference_name, ""),
				"action": frappe.utils.strip_html(t.description or "")[:120],
				"by": frappe.utils.get_fullname(t.allocated_to) if t.allocated_to else "",
			}
			for t in todos
			if t.reference_name in customers
		],
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


def _pipeline(sp=None):
	"""Principal-wise leads at their latest stage (rows of the Application Development Status report)."""
	from techpark.techpark.report.application_development_status.application_development_status import get_data

	rows = get_data(frappe._dict(visited_by=sp) if sp else frappe._dict())
	counts = {stage: 0 for stage in _pipeline_order()}
	for r in rows:
		if r.get("lead_stage") in counts:
			counts[r["lead_stage"]] += 1
	return {
		"stages": [{"stage": s, "value": counts[s]} for s in counts],
		"trials": counts.get("Trial PO Received", 0) + counts.get("Sample Received", 0) + counts.get("Trial in Progress", 0),
		"successful": counts.get("Successful Trial", 0),
		"won": counts.get("Bulk Trial PO", 0),
		"regularization": counts.get("Regularization", 0),
		# Sales cycle follow-ups: lines waiting on an enquiry / order / delivery / payment
		"follow_ups": [{"status": s, "value": counts[s]} for s in ("Enquiry Follow-up", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up")],
	}


def _customers(sp=None):
	filters = {}
	if sp:  # 2026-11-23: the customers that sales person handles
		filters["name"] = ("in", frappe.get_all("Customer Agent", filters={"parenttype": "TP Customer", "agent": sp}, pluck="parent") or [""])
	customers = frappe.get_list(
		"TP Customer", filters=filters, fields=["customer_status", "territory_region"], limit_page_length=0
	)
	count = lambda status: sum(1 for c in customers if c.customer_status == status)
	return {
		"total": len(customers),
		"active": count("Active Customer"),
		"prospects": count("Prospect"),
		# 2026-11-23: a card for every status
		"under_development": count("Under Development"),
		"inactive": count("Inactive"),
		"by_status": _group(customers, "customer_status"),
		"by_region": _group(customers, "territory_region"),
	}


def _sales_people():
	"""2026-11-23: enabled users with a sales role, for the admin's Sales Person filter."""
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ("in", list(__import__("techpark.roles", fromlist=["app_roles"]).app_roles()))}, pluck="parent", distinct=True
	)
	# 2026-11-23: admins (e.g. Milind Lokare) stay users but are not in the Sales Person dropdown
	# 2026-11-26: only TechPark Approvers (Abhijeet, Milind) are left out; Santosh is a System Manager but also a
	# salesperson (manager of Shiv and Vedant), so he stays in the list
	admins = set(frappe.get_all("Has Role", filters={"parenttype": "User", "role": __import__("techpark.roles", fromlist=["approver_role"]).approver_role()}, pluck="parent"))
	users = [u for u in users if u not in admins]
	return [
		{"value": u.name, "label": u.full_name or u.name}
		for u in frappe.get_all(
			"User", filters={"name": ("in", users or [""]), "enabled": 1, "user_type": "System User"}, fields=["name", "full_name"], order_by="full_name"
		)
		if u.name not in ("Administrator", "Guest")
	]


def _expenses(month_start, since, sp=None):
	own = {"employee": sp} if sp else {}
	expenses = frappe.get_list(
		"TP Expense",
		filters={"entry_date": (">=", since), **own},
		fields=["entry_date", "employee_name", "status", "total_amount", "passed_amount"],
		limit_page_length=0,
	)
	this_month = [e for e in expenses if getdate(e.entry_date) >= month_start]
	pending = frappe.get_list("TP Expense", filters={"status": ("in", EXPENSE_PENDING), **own}, fields=["total_amount"])
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
