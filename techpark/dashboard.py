# Copyright (c) 2026, Techpark International
"""TechPark dashboard: the "TechPark Today" panel at the top of the TechPark workspace.

The panel is a Custom HTML Block whose HTML / CSS / JS live in techpark/dashboard_block/
and are copied into the block on every migrate (sync_dashboard_block), so it ships with the app.
get_today() feeds it: what needs attention now. Sales users see their own work,
Sales Managers / System Managers see the whole team.
"""

import os

import frappe
from frappe import _
from frappe.utils import add_days, add_months, get_first_day, get_fullname, getdate, today

BLOCK_NAME = "TechPark Today"
BLOCK_DIR = os.path.join(os.path.dirname(__file__), "dashboard_block")
MANAGER_ROLES = {"Sales Manager", "System Manager"}
PROSPECT_STALE_DAYS = 7


def sync_dashboard_block():
	"""after_migrate: create / update the Custom HTML Block from the files in dashboard_block/."""

	def read(name):
		with open(os.path.join(BLOCK_DIR, name), encoding="utf-8") as f:
			return f.read()

	values = {"html": read("today.html"), "style": read("today.css"), "script": read("today.js"), "private": 0}
	if frappe.db.exists("Custom HTML Block", BLOCK_NAME):
		block = frappe.get_doc("Custom HTML Block", BLOCK_NAME)
		block.update(values)
		block.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": "Custom HTML Block", "name": BLOCK_NAME, **values}).insert(
			ignore_permissions=True, set_name=BLOCK_NAME
		)


@frappe.whitelist()
def get_today():
	user = frappe.session.user
	team = bool(MANAGER_ROLES & set(frappe.get_roles(user)))
	now = getdate(today())

	follow_ups = _open_follow_ups(user, team, now)
	return {
		"user_name": (get_fullname(user) or user).split(" ")[0],
		"scope": _("Team") if team else _("My"),
		"team": team,
		"today": str(now),
		"counts": {
			"overdue": sum(1 for f in follow_ups if f["state"] == "overdue"),
			"due_today": sum(1 for f in follow_ups if f["state"] == "today"),
			"stale_prospects": _stale_prospects(user, team, now),
		},
		"follow_ups": follow_ups[:8],
		"follow_ups_total": len(follow_ups),
		"recent_visits": _recent_visits(user, team),
		"visits": _visit_trend(user, team, now),
		"prospect_cutoff": str(add_days(now, -PROSPECT_STALE_DAYS)),
	}


@frappe.whitelist()
def get_overdue_follow_ups_card(filters=None):
	"""'Overdue Follow-ups' number card: counted the same way as the overdue tile in the panel,
	so the two never disagree (follow-ups of cancelled visits are left out)."""
	user = frappe.session.user
	team = bool(MANAGER_ROLES & set(frappe.get_roles(user)))
	now = getdate(today())
	route_options = {"reference_type": "Daily Visit Report", "status": "Open", "date": ["<", str(now)]}
	if not team:
		route_options["allocated_to"] = user
	return {
		"value": sum(1 for f in _open_follow_ups(user, team, now) if f["state"] == "overdue"),
		"fieldtype": "Int",
		"route": ["List", "ToDo"],
		"route_options": route_options,
	}


@frappe.whitelist()
def close_follow_up(todo):
	"""'Done' on a follow-up in the panel: close its ToDo (only the assignee or a manager)."""
	doc = frappe.get_doc("ToDo", todo)
	if doc.reference_type != "Daily Visit Report":
		frappe.throw(_("Not a visit follow-up."))
	is_manager = bool(MANAGER_ROLES & set(frappe.get_roles()))
	if doc.allocated_to != frappe.session.user and not is_manager:
		frappe.throw(_("Only {0} can close this follow-up.").format(get_fullname(doc.allocated_to)), frappe.PermissionError)
	doc.status = "Closed"
	doc.save(ignore_permissions=True)
	return doc.name


def _open_follow_ups(user, team, now):
	filters = {"reference_type": "Daily Visit Report", "status": "Open"}
	if not team:
		filters["allocated_to"] = user
	todos = frappe.get_all(
		"ToDo",
		filters=filters,
		fields=["name", "date", "reference_name", "allocated_to"],
		order_by="date asc",
		limit=200,
	)
	visits = {
		v.name: v
		for v in frappe.get_all(
			"Daily Visit Report",
			filters={"name": ("in", [t.reference_name for t in todos] or [""]), "docstatus": 1},
			fields=["name", "customer", "customer_name", "next_action", "principal"],
		)
	}
	rows = []
	for t in todos:
		visit = visits.get(t.reference_name)
		if not visit:
			continue  # visit cancelled
		due = getdate(t.date) if t.date else None
		state = "later"
		if due and due < now:
			state = "overdue"
		elif due == now:
			state = "today"
		elif due and due <= add_days(now, 7):
			state = "week"
		rows.append(
			{
				"todo": t.name,
				"visit": visit.name,
				"customer": visit.customer,
				"customer_name": visit.customer_name,
				"action": visit.next_action,
				"principal": visit.principal,
				"due": str(due) if due else None,
				"days": (due - now).days if due else None,
				"state": state,
				"owner": get_fullname(t.allocated_to) if team else None,
			}
		)
	order = {"overdue": 0, "today": 1, "week": 2, "later": 3}
	rows.sort(key=lambda r: (order[r["state"]], r["due"] or "9999"))
	return rows


def _stale_prospects(user, team, now):
	filters = {"customer_status": "Prospect", "prospect_since": ("<=", add_days(now, -PROSPECT_STALE_DAYS))}
	if not team:
		mine = frappe.get_all("Customer Agent", filters={"parenttype": "TP Customer", "agent": user}, pluck="parent")
		filters["name"] = ("in", mine or [""])
	return frappe.db.count("TP Customer", filters)


def _recent_visits(user, team):
	filters = {"docstatus": ("<", 2)}
	if not team:
		filters["visited_by"] = user
	return frappe.get_all(
		"Daily Visit Report",
		filters=filters,
		fields=[
			"name", "visit_date", "customer_name", "visit_purpose", "principal", "lead_status", "lead_stage",
			"docstatus", "employee_name",
		],
		order_by="visit_date desc, creation desc",
		limit=6,
	)


def _visit_trend(user, team, now):
	def count(start, end):
		filters = {"docstatus": 1, "visit_date": ("between", [start, end])}
		if not team:
			filters["visited_by"] = user
		return frappe.db.count("Daily Visit Report", filters)

	this_start = get_first_day(now)
	last_start = add_months(this_start, -1)
	# Compare like for like: last month up to the same day of the month
	last_same_day = min(add_months(now, -1), add_days(this_start, -1))
	return {"this_month": count(this_start, now), "last_month_to_date": count(last_start, last_same_day)}
