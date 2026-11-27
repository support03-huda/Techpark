# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""Record-level access: every user sees only their own Daily Visit Reports (and those they joined);
admins see everyone's. Visit Reports lock for salespeople a set
number of days after they were entered (TechPark Settings).

2026-11-26: a manager also sees the customers, visits and lines of who reports to them (TP Team Member:
Reports To, and Reports To by Principal for single principals).
Expenses follow the reporting line (TP Team Member): approvers and admins see all of them,
a manager sees their own and those of the people reporting to them, everybody else only their own."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

# 2026-11-26: admin roles = TechPark Settings > Roles > Admin Roles (see every DVR / dashboard, change locked entries)
# Actions the lock takes away from a salesperson.
LOCKED_PTYPES = {"write", "submit", "cancel", "delete", "amend"}
# Final approval of expenses: the same Admin Roles (2026-11-26)
# Kinds of access that only read a record.
READ_PTYPES = (None, "read", "print", "email", "report", "export")


def is_manager(user=None):
	user = user or frappe.session.user
	from techpark.roles import admin_roles

	return user == "Administrator" or bool(admin_roles() & set(frappe.get_roles(user)))


def has_app_permission():
	"""TechPark tile on the apps screen: salespeople, managers and admins."""
	user = frappe.session.user
	from techpark.roles import admin_roles, app_roles

	return user == "Administrator" or bool((admin_roles() | app_roles()) & set(frappe.get_roles(user)))


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
	# 2026-11-26: and the visits of who reports to them (for those principals)
	team = _team_parts(
		user,
		lambda m: f"`tabDaily Visit Report`.visited_by = {frappe.db.escape(m)}",
		lambda ps: f"`tabDaily Visit Report`.principal in {sql_list(ps)}",
		lambda ps: f"ifnull(`tabDaily Visit Report`.principal, '') not in {sql_list(ps)}",
	)
	user = frappe.db.escape(user)
	return (
		f"(`tabDaily Visit Report`.visited_by = {user} or `tabDaily Visit Report`.owner = {user}"
		f" or exists (select 1 from `tabDVR Joint Visitor` j where j.parenttype = 'Daily Visit Report'"
		f" and j.parent = `tabDaily Visit Report`.name and j.user = {user})"
		+ "".join(" or " + t for t in team) + ")"
	)


def dvr_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	# A new DVR is always the user's own (validate sets Employee to them).
	if is_manager(user) or doc.is_new():
		return True
	if user not in (doc.visited_by, doc.owner):
		# A colleague on a joint visit may read it (the visit stays its Employee's)
		if ptype in READ_PTYPES and user in {r.user for r in doc.get("joint_visitors") or []}:
			return True
		# 2026-11-26: their manager (Reports To / by Principal) may read it
		return ptype in READ_PTYPES and bool(
			frappe.db.sql(f"select 1 from `tabDaily Visit Report` where name = %s and {dvr_query_conditions(user)}", doc.name)
		)
	return not (ptype in LOCKED_PTYPES and is_locked(doc, user))


# Field naming the salesperson a record belongs to (besides its owner).
OWN_FIELDS = {"TP Opportunity": "sales_person"}


def _own_conditions(doctype, user):
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	field = OWN_FIELDS[doctype]
	# 2026-11-26: and the lines of who reports to them (for those principals)
	team = _team_parts(
		user,
		lambda m: f"`tab{doctype}`.`{field}` = {frappe.db.escape(m)}",
		lambda ps: f"`tab{doctype}`.principal in {sql_list(ps)}",
		lambda ps: f"ifnull(`tab{doctype}`.principal, '') not in {sql_list(ps)}",
	)
	user = frappe.db.escape(user)
	return f"(`tab{doctype}`.`{field}` = {user} or `tab{doctype}`.owner = {user}" + "".join(" or " + t for t in team) + ")"


def opportunity_query_conditions(user=None, doctype=None):
	return _own_conditions("TP Opportunity", user)


def own_record_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_manager(user) or ptype == "create" or doc.is_new():
		return True
	if user in (doc.get(OWN_FIELDS[doc.doctype]), doc.owner):
		return True
	# 2026-11-26: their manager may read it
	return ptype in READ_PTYPES and bool(
		frappe.db.sql(f"select 1 from `tab{doc.doctype}` where name = %s and {_own_conditions(doc.doctype, user)}", doc.name)
	)


def is_expense_admin(user=None):
	user = user or frappe.session.user
	return is_manager(user)  # 2026-11-26: Admin Roles


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


# 2026-11-23: a salesperson sees only the customers whose Handled By (Employee) has them; admins see all
def _handled_by(user):
	return (
		"exists (select 1 from `tabCustomer Agent` a where a.parenttype = 'TP Customer'"
		f" and a.parent = `tabTP Customer`.name and a.agent = {frappe.db.escape(user)})"
	)


def _has_principal(principal):
	return (
		"exists (select 1 from `tabCustomer Principal` p where p.parenttype = 'TP Customer'"
		f" and p.parent = `tabTP Customer`.name and p.principal = {frappe.db.escape(principal)})"
	)


# 2026-11-26: Reports To / Reports To by Principal (TP Team Member) -> what a manager sees of their team
def reporting(user):
	"""[(member, only_principals, except_principals)] of the people reporting to `user`:
	Reports To = user -> all their work except the principals they report elsewhere for;
	Reports To by Principal = user -> only those principals."""
	if not frappe.db.table_exists("TP Reporting Line"):
		return []
	members = frappe.get_all("TP Team Member", filters={"inactive": 0, "user": ("!=", user)}, fields=["name", "user", "reports_to"])
	lines = {}
	for row in frappe.get_all("TP Reporting Line", filters={"parenttype": "TP Team Member"}, fields=["parent", "principal", "reports_to"]):
		lines.setdefault(row.parent, []).append(row)
	out = []
	for m in members:
		rows = lines.get(m.name, [])
		if m.reports_to == user:
			out.append((m.user, None, [r.principal for r in rows if r.reports_to != user]))
		else:
			mine = [r.principal for r in rows if r.reports_to == user]
			if mine:
				out.append((m.user, mine, None))
	return out


def _team_parts(user, person, has_principal, lacks_principal):
	"""SQL parts: a reporting member's records, limited to the principals that report to `user`."""
	parts = []
	for member, only, except_ in reporting(user):
		cond = person(member)
		if only:
			cond += " and " + has_principal(only)
		elif except_:
			cond += " and " + lacks_principal(except_)
		parts.append(f"({cond})")
	return parts


def _customer_has_any(principals):
	return (
		"exists (select 1 from `tabCustomer Principal` p where p.parenttype = 'TP Customer'"
		f" and p.parent = `tabTP Customer`.name and p.principal in {sql_list(principals)})"
	)


def _customer_has_other(principals):
	"""no principal yet, or one that is not reported elsewhere"""
	return (
		"(not exists (select 1 from `tabCustomer Principal` p where p.parenttype = 'TP Customer' and p.parent = `tabTP Customer`.name)"
		" or exists (select 1 from `tabCustomer Principal` p where p.parenttype = 'TP Customer'"
		f" and p.parent = `tabTP Customer`.name and p.principal not in {sql_list(principals)}))"
	)


def customer_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	# 2026-11-25: TechPark Settings > Customer Access: also the customers of a principal and/or of a colleague
	parts = [_handled_by(user)]
	parts += _team_parts(user, _handled_by, _customer_has_any, _customer_has_other)  # 2026-11-26: their team's
	for rule in frappe.get_all("TP Customer Access", filters={"parent": "TechPark Settings", "user": user}, fields=["principal", "customers_of"]):
		cond = [c for c in (rule.principal and _has_principal(rule.principal), rule.customers_of and _handled_by(rule.customers_of)) if c]
		if cond:
			parts.append("(" + " and ".join(cond) + ")")
	return "(" + " or ".join(parts) + ")"


def customer_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_manager(user) or doc.is_new() or ptype == "create":
		return True
	if user in {r.agent for r in doc.get("handled_by") or []}:
		return True
	# 2026-11-25: the same rules as the list
	return bool(frappe.db.sql(f"select 1 from `tabTP Customer` where name = %s and {customer_query_conditions(user)}", doc.name))


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
