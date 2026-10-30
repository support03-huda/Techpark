# Copyright (c) 2026, Techpark International
"""Number cards of the TechPark workspace ("Custom" type).

Follow-up cards count open visit follow-ups (follow-ups of cancelled visits are left out); lead
cards count principal-wise leads at their latest status, the same rows as the Application
Development Status report, so a card never disagrees with what it opens. Sales users see
their own work, managers the whole team.
"""

import frappe
from frappe.utils import add_days, getdate, today

MANAGER_ROLES = {"Sales Manager", "System Manager"}
PROSPECT_STALE_DAYS = 7
LEAD_REPORT = "Application Development Status"


@frappe.whitelist()
def get_overdue_follow_ups_card(filters=None):
	return _follow_up_card("overdue", "<")


@frappe.whitelist()
def get_follow_ups_due_today_card(filters=None):
	return _follow_up_card("today", "=")


@frappe.whitelist()
def get_stale_prospects_card(filters=None):
	user, team, now = _scope()
	return {
		"value": _stale_prospects(user, team, now),
		"fieldtype": "Int",
		"route": ["List", "TP Customer"],
		"route_options": {
			"customer_status": "Prospect",
			"prospect_since": ["<=", str(add_days(now, -PROSPECT_STALE_DAYS))],
		},
	}


@frappe.whitelist()
def get_trials_in_progress_card(filters=None):
	return _lead_card(("Sample / Trial Planned", "Trial in Progress"), stage="Development")


@frappe.whitelist()
def get_successful_trials_card(filters=None):
	"""Trial done, no sales status yet: ready for a quotation."""
	return _lead_card(("Successful Trial",), status="Successful Trial")


@frappe.whitelist()
def get_orders_won_card(filters=None):
	return _lead_card(("Order Won",), status="Order Won")


@frappe.whitelist()
def get_regularization_card(filters=None):
	return _lead_card(("Regularization",), status="Regularization")


def _scope():
	user = frappe.session.user
	return user, bool(MANAGER_ROLES & set(frappe.get_roles(user))), getdate(today())


def _follow_up_card(state, date_operator):
	user, team, now = _scope()
	route_options = {"reference_type": "Daily Visit Report", "status": "Open", "date": [date_operator, str(now)]}
	if not team:
		route_options["allocated_to"] = user
	return {
		"value": sum(1 for s in _open_follow_up_states(user, team, now) if s == state),
		"fieldtype": "Int",
		"route": ["List", "ToDo"],
		"route_options": route_options,
	}


def _open_follow_up_states(user, team, now):
	""""overdue" / "today" / "later" of every open follow-up of a submitted visit."""
	filters = {"reference_type": "Daily Visit Report", "status": "Open"}
	if not team:
		filters["allocated_to"] = user
	todos = frappe.get_all("ToDo", filters=filters, fields=["date", "reference_name"], limit=500)
	submitted = set(
		frappe.get_all(
			"Daily Visit Report",
			filters={"name": ("in", [t.reference_name for t in todos] or [""]), "docstatus": 1},
			pluck="name",
		)
	)
	states = []
	for t in todos:
		if t.reference_name not in submitted:
			continue  # visit cancelled
		due = getdate(t.date) if t.date else None
		states.append("overdue" if due and due < now else "today" if due == now else "later")
	return states


def _stale_prospects(user, team, now):
	filters = {"customer_status": "Prospect", "prospect_since": ("<=", add_days(now, -PROSPECT_STALE_DAYS))}
	if not team:
		mine = frappe.get_all("Customer Agent", filters={"parenttype": "TP Customer", "agent": user}, pluck="parent")
		filters["name"] = ("in", mine or [""])
	return frappe.db.count("TP Customer", filters)


def _lead_card(statuses, stage=None, status=None):
	from techpark.techpark.report.application_development_status.application_development_status import get_data

	# get_data applies the DVR permissions: a salesperson counts only their own leads.
	rows = get_data(frappe._dict())
	route_options = {"open_only": 0}
	if stage:
		route_options["stage"] = stage
	if status:
		route_options["status"] = status
	return {
		"value": sum(1 for r in rows if r["lead_stage"] in statuses),
		"fieldtype": "Int",
		"route": ["query-report", LEAD_REPORT],
		"route_options": route_options,
	}
