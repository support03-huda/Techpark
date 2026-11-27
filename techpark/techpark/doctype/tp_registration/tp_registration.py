# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""TP Registration — a login made through Sign Up, approved or rejected once by an approver.

On approval the approver picks the role and, when the person is an existing employee,
the Employee record the login belongs to. The person then gets the set-password email.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from techpark.login import home  # 2026-11-26: settings
from techpark.roles import approver_role, registration_choices  # 2026-11-26: settings
from techpark.registration import find_employee_by_email, get_free_employees, is_approver

# 2026-11-26: Approver Role, Email From and the approval choices are in TechPark Settings (were hard coded)


def registration_sender():
	"""2026-11-26: "TechPark <support@...>" from TechPark Settings."""
	from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

	email, name = get_setting("email_from"), get_setting("email_sender_name")
	return f"{name} <{email}>" if name and email else email or None


class TPRegistration(Document):
	def onload(self):
		self.set_onload("can_decide", is_approver())
		if self.status == "Pending" and is_approver():
			self.set_onload("role_choices", list(registration_choices()))
			self.set_onload("matched_employee", find_employee_by_email(self.email, self.user))
			self.set_onload("employees", get_free_employees(self.user))

	def check_can_decide(self):
		if not is_approver():
			frappe.throw(_("Only an approver can approve or reject a registration."), frappe.PermissionError)
		if self.status != "Pending":
			frappe.throw(_("This registration is already {0}.").format(_(self.status).lower()))

	@frappe.whitelist()
	def approve(self, role, existing_employee=0, employee=None):
		self.check_can_decide()
		choices = registration_choices()
		if role not in choices:
			frappe.throw(_("Choose one of: {0}.").format(", ".join(choices)))
		existing_employee = cint(existing_employee)
		if existing_employee and not employee:
			frappe.throw(_("Select the employee, or untick Existing Employee."))

		user = frappe.get_doc("User", self.user)
		user.user_type = "System User"
		user.enabled = 1
		current = {row.role for row in user.roles}
		for new_role in choices[role]:
			if new_role not in current:
				user.append("roles", {"role": new_role})
		# Approvers may not edit users themselves; this one change is checked above.
		user.save(ignore_permissions=True)

		if existing_employee:
			self.link_employee(employee)

		self.status = "Approved"
		self.role_given = role
		self.existing_employee = existing_employee
		self.employee = employee if existing_employee else None
		self.decided_by = frappe.session.user
		self.decided_on = now_datetime()
		self.save(ignore_permissions=True)

		return {"mail_sent": self.send_welcome_mail(user, role)}

	def link_employee(self, employee):
		record = frappe.get_doc("Employee", employee)
		if record.user_id and record.user_id != self.user:
			frappe.throw(_("Employee {0} already belongs to login {1}.").format(employee, record.user_id))
		record.user_id = self.user
		# Older employee records may miss fields that are mandatory today.
		record.flags.ignore_mandatory = True
		record.save(ignore_permissions=True)

	def send_welcome_mail(self, user, role):
		"""Welcome email with the set-password link; after setting it the person lands on the TechPark Dashboard."""
		if not has_outgoing_email():
			return False
		# Where /update-password sends the person once the password is set.
		frappe.db.set_value("User", user.name, "redirect_url", frappe.utils.get_url(home()))
		frappe.cache.hdel("redirect_after_login", user.name)
		link = user._reset_password()
		message = f"""
			<p>{_("Dear {0},").format(frappe.utils.escape_html(self.full_name or self.email))}</p>
			<p>{_("Welcome to TechPark! Your registration has been approved with the role <b>{0}</b>.").format(role)}</p>
			<p>{_("Click the button below to set your password. After that you will be taken straight to the TechPark desk.")}</p>
			<p><a href="{link}" style="display:inline-block;padding:10px 18px;background:#2490ef;color:#fff;
				border-radius:6px;text-decoration:none">{_("Set Password")}</a></p>
			<p style="color:#888">{_("Your login ID: {0}").format(self.email)}<br>
				{_("If the button does not work, open this link: {0}").format(link)}</p>
		"""
		return self.send_mail(_("Welcome to TechPark – set your password"), message)

	def send_rejection_mail(self):
		if not has_outgoing_email():
			return False
		reason = (
			f"<p>{_('Reason')}: {frappe.utils.escape_html(self.remarks)}</p>" if self.remarks else ""
		)
		message = f"""
			<p>{_("Dear {0},").format(frappe.utils.escape_html(self.full_name or self.email))}</p>
			<p>{_("Your registration for TechPark has been <b>rejected</b> by the administrator.")}</p>
			{reason}
			<p>{_("If you think this is a mistake, please contact the TechPark administrator.")}</p>
		"""
		return self.send_mail(_("TechPark registration rejected"), message)

	def send_mail(self, subject, message):
		try:
			frappe.sendmail(
				recipients=[self.email],
				sender=registration_sender(),  # 2026-11-26: TechPark Settings > Email Sender Name / Email From
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=True,
			)
			return True
		except Exception:
			frappe.log_error(title=f"TechPark registration email failed: {subject}")
			return False

	@frappe.whitelist()
	def reject(self, remarks=None):
		self.check_can_decide()
		frappe.db.set_value("User", self.user, "enabled", 0)
		self.status = "Rejected"
		self.remarks = remarks
		self.decided_by = frappe.session.user
		self.decided_on = now_datetime()
		self.save(ignore_permissions=True)
		return {"mail_sent": self.send_rejection_mail()}


def has_outgoing_email():
	"""An enabled default outgoing Email Account, or a mail server in the site config."""
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
		or frappe.conf.get("mail_server")
	)
