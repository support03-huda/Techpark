# Copyright (c) 2026, Techpark International
"""Record-level access: every user sees only their own Daily Visit Reports (and those they joined);
admins see everyone's. Visit Reports lock for salespeople a set
number of days after they were entered (TechPark Settings).

Expenses follow the reporting line (TP Team Member): approvers and admins see all of them,
a manager sees their own and those of the people reporting to them, everybody else only their own."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

# Admin roles: see every DVR / dashboard and may change locked entries.
MANAGER_ROLES = {"TechPark Approver", "System Manager"}
# Actions the lock takes away from a salesperson.
LOCKED_PTYPES = {"write", "submit", "cancel", "delete", "amend"}
# Roles that give the final approval of expenses and see everybody's.
EXPENSE_ADMIN_ROLES = {"TechPark Approver", "System Manager"}
# Kinds of access that only read a record.
READ_PTYPES = (None, "read", "print", "email", "report", "export")


def is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(MANAGER_ROLES & set(frappe.get_roles(user)))


def has_app_permission():
	"""TechPark tile on the apps screen: salespeople, managers and admins."""
	user = frappe.session.user
	return user == "Administrator" or bool((MANAGER_ROLES | {"Sales Manager", "Sales User"}) & set(frappe.get_roles(user)))


def is_locked(doc, user=None):
	"""True when `user` (a salesperson) may no longer change this entry."""
	if doc.is_new() or is_manager(user):
		return False
	from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

	return date_diff(today(), getdate(doc.creation)) >= get_setting("lock_days")


def check_lock(doc, method=None):
	"""Hook (validate / before_cancel / on_trash): refuse changes to a locked entry."""
	if is_locked(doc):
		from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

		frappe.throw(
			_("{0} {1} is locked: entries older than {2} days can only be changed by a Sales Manager or an admin.").format(
				_(doc.doctype), frappe.bold(doc.name), get_setting("lock_days")
			),
			frappe.PermissionError,
		)


def dvr_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	user = frappe.db.escape(user)
	return (
		f"(`tabDaily Visit Report`.visited_by = {user} or `tabDaily Visit Report`.owner = {user}"
		f" or exists (select 1 from `tabDVR Joint Visitor` j where j.parenttype = 'Daily Visit Report'"
		f" and j.parent = `tabDaily Visit Report`.name and j.user = {user}))"
	)


def dvr_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	# A new DVR is always the user's own (validate sets Employee to them).
	if is_manager(user) or doc.is_new():
		return True
	if user not in (doc.visited_by, doc.owner):
		# A colleague on a joint visit may read it (the visit stays its Employee's)
		return ptype in READ_PTYPES and user in {r.user for r in doc.get("joint_visitors") or []}
	return not (ptype in LOCKED_PTYPES and is_locked(doc, user))


# Field naming the salesperson a record belongs to (besides its owner).
OWN_FIELDS = {"TP Opportunity": "sales_person"}


def _own_conditions(doctype, user):
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	user = frappe.db.escape(user)
	return f"(`tab{doctype}`.`{OWN_FIELDS[doctype]}` = {user} or `tab{doctype}`.owner = {user})"


def opportunity_query_conditions(user=None, doctype=None):
	return _own_conditions("TP Opportunity", user)


def own_record_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_manager(user) or ptype == "create" or doc.is_new():
		return True
	return user in (doc.get(OWN_FIELDS[doc.doctype]), doc.owner)


def is_expense_admin(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(EXPENSE_ADMIN_ROLES & set(frappe.get_roles(user)))


def get_team(user):
	"""The user first, then the active people whose Reports To is the user."""
	if not user:
		return []
	members = frappe.get_all(
		"TP Team Member", filters={"reports_to": user, "inactive": 0, "user": ["!=", user]}, pluck="user"
	)
	return [user, *members]


def can_approve_expenses(user=None):
	"""Approvers and admins, and anybody somebody reports to."""
	user = user or frappe.session.user
	return is_expense_admin(user) or len(get_team(user)) > 1


def get_visible_users(user=None):
	"""Whose expenses the user may see: None means everybody (expense admin)."""
	user = user or frappe.session.user
	if is_expense_admin(user):
		return None
	return get_team(user)


def sql_list(values):
	return "(" + ", ".join(frappe.db.escape(v) for v in values) + ")"


def expense_query_conditions(user=None, doctype=None):
	team = get_visible_users(user)
	if team is None:
		return ""
	return f"`tabTP Expense`.employee in {sql_list(team)}"


def expense_has_permission(doc, ptype=None, user=None):
	# Anyone with the role may create an expense (it is always their own).
	if ptype == "create" or doc.is_new():
		return True
	team = get_visible_users(user)
	if team is None:
		return True
	# A manager may look at the team's expenses; they approve through TPExpense.approve.
	if ptype in READ_PTYPES:
		return doc.employee in team
	return doc.employee == team[0]


def pending_work_query_conditions(user=None, doctype=None):
	"""Pending Work: people see what they are responsible for or raised; admins see all."""
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	user = frappe.db.escape(user)
	return (
		f"(`tabTP Pending Work`.owner = {user} or exists (select 1 from `tabTP Pending Work User` r"
		f" where r.parenttype = 'TP Pending Work' and r.parent = `tabTP Pending Work`.name and r.user = {user}))"
	)


def pending_work_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_manager(user) or doc.is_new() or ptype == "create":
		return True
	return user == doc.owner or user in {r.user for r in doc.get("responsible") or []}
