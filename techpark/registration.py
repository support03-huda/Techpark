# Copyright (c) 2026, Techpark International
"""Approval of self-registered logins.

A login made through Sign Up (/login#signup) gets a TP Registration and cannot be used
until an approver (Milind / Abhijeet, role "TechPark Approver") approves it. The
set-password email is sent only on approval.
"""

import frappe
from frappe import _

APPROVER_ROLE = "TechPark Approver"
# First names of the users who approve registrations (the client's admins).
APPROVER_FIRST_NAMES = ("Abhijeet", "Milind")


def is_approver(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or APPROVER_ROLE in frappe.get_roles(user)


def get_approvers():
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": APPROVER_ROLE}, pluck="parent", distinct=True
	)
	return [u for u in users if u != "Administrator" and frappe.db.get_value("User", u, "enabled")]


def find_employee_by_email(email, user=None):
	"""Active Employee with this email and no other login, or None."""
	if not email:
		return None
	matches = frappe.db.sql(
		"""
		select name from `tabEmployee`
		where %(email)s in (lower(trim(ifnull(company_email, ''))), lower(trim(ifnull(personal_email, ''))),
			lower(trim(ifnull(prefered_email, ''))))
			and (ifnull(user_id, '') = '' or user_id = %(user)s)
		order by status = 'Active' desc, name
		""",
		{"email": email.strip().lower(), "user": user or ""},
	)
	return matches[0][0] if matches else None


def get_free_employees(user=None):
	"""Active employees without a login (or with `user`), for the approval dialog."""
	return frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		or_filters=[["user_id", "is", "not set"], ["user_id", "=", user or ""]],
		fields=["name", "employee_name", "designation", "department"],
		order_by="employee_name",
	)


def on_user_before_insert(doc, method=None):
	"""No set-password email at Sign Up; it goes out on approval."""
	if frappe.session.user != "Guest":
		return
	doc.send_welcome_email = 0
	doc.flags.no_welcome_mail = True


def on_user_insert(doc, method=None):
	"""A login created by a visitor through Sign Up waits for approval."""
	if frappe.session.user != "Guest" or frappe.db.exists("TP Registration", {"user": doc.name}):
		return

	registration = frappe.get_doc(
		{
			"doctype": "TP Registration",
			"user": doc.name,
			"full_name": doc.full_name or doc.first_name or doc.name,
			"email": doc.email,
			"status": "Pending",
		}
	).insert(ignore_permissions=True)
	notify_approvers(registration)


def notify_approvers(registration):
	# A failing notification must never stop the sign up.
	try:
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		approvers = get_approvers()
		if not approvers:
			return
		enqueue_create_notification(
			approvers,
			{
				"type": "Alert",
				"document_type": "TP Registration",
				"document_name": registration.name,
				"subject": _("New login waiting for approval: {0} ({1})").format(
					registration.full_name, registration.email
				),
				"from_user": "Administrator",
			},
		)
	except Exception:
		frappe.log_error(title="TechPark registration notification failed")


def check_approval(login_manager):
	"""on_login: a self-registered login works only once approved."""
	status = frappe.db.get_value("TP Registration", {"user": login_manager.user}, "status")
	if status == "Pending":
		frappe.throw(
			_("Your registration is waiting for approval. You can log in once an administrator has approved it."),
			frappe.AuthenticationError,
		)
	if status == "Rejected":
		frappe.throw(
			_("Your registration was not approved. Please contact the administrator."), frappe.AuthenticationError
		)


def setup():
	"""Approver role for Milind and Abhijeet, and Sign Up switched on."""
	if not frappe.db.exists("Role", APPROVER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": APPROVER_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)

	for first_name in APPROVER_FIRST_NAMES:
		users = frappe.get_all(
			"User",
			filters={"first_name": first_name, "enabled": 1, "user_type": "System User"},
			pluck="name",
		)
		for name in users:
			user = frappe.get_doc("User", name)
			if APPROVER_ROLE not in [r.role for r in user.roles]:
				user.add_roles(APPROVER_ROLE)
			print(f"{APPROVER_ROLE}: {name}")
		if not users:
			print(f"{APPROVER_ROLE}: no enabled user named {first_name}; give the role by hand")

	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
