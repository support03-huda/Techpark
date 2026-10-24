# Copyright (c) 2026, Techpark International
"""Record-level access: a Sales User sees only their own Daily Visit Reports;
Sales Managers and admins see everyone's. Visit Reports lock for salespeople a set
number of days after they were entered (TechPark Settings)."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

# Roles that see every DVR and may change locked entries.
MANAGER_ROLES = {"Sales Manager", "TechPark Approver", "System Manager"}
# Actions the lock takes away from a salesperson.
LOCKED_PTYPES = {"write", "submit", "cancel", "delete", "amend"}


def is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(MANAGER_ROLES & set(frappe.get_roles(user)))


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
	return f"(`tabDaily Visit Report`.visited_by = {user} or `tabDaily Visit Report`.owner = {user})"


def dvr_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	# A new DVR is always the user's own (validate sets Employee to them).
	if is_manager(user) or doc.is_new():
		return True
	if user not in (doc.visited_by, doc.owner):
		return False
	return not (ptype in LOCKED_PTYPES and is_locked(doc, user))
