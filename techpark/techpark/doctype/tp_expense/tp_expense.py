# Copyright (c) 2026, Techpark International
"""TP Expense — an expense claim with its bills, and the approval steps
Draft -> Pending Manager -> Pending Admin -> Approved.

The employee sends the claim; the person they report to (TP Team Member) approves it, then a
TechPark Approver gives the final approval and may lower the passed amount of a bill. Either
can reject it back to the employee with a reason. Every step notifies the employee, their
manager and the approvers. Without a manager the claim goes straight to the approvers."""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import cstr, flt, get_fullname, getdate, now_datetime

from techpark.permission import get_team, get_visible_users, is_expense_admin, sql_list

# Fields only the approval methods may change.
STATUS_FIELDS = ("status", "sent_on", "approved_by", "approved_on", "authorized_by", "authorized_on", "rejection_reason")
# Until the approver's step the passed amount simply follows the amount.
FOLLOW_AMOUNT_STATUSES = ("Draft", "Pending Manager")
# Steps the list / approvals page may run on many expenses at once (reject needs a reason).
BULK_ACTIONS = ("send_for_approval", "approve", "unapprove")
# Most expenses in the Team History of the Expense Approvals page.
HISTORY_LIMIT = 200
# Role that gives the final approval.
APPROVER_ROLE = "TechPark Approver"
# First month of the financial year (April).
FINANCIAL_YEAR_START = 4


class TPExpense(Document):
	def autoname(self):
		# EXP-2627-000001: financial year of the entry date + running number per year
		year = financial_year(self.entry_date)
		self.name = f"EXP-{year}-{getseries(f'TP-EXP-{year}-', 6)}"

	def onload(self):
		# The form shows only the buttons of the steps the user may take.
		self.set_onload("actions", self.allowed_actions())

	def before_insert(self):
		self.set_employee()
		# Every new expense starts as a draft, also when copied or sent through the API.
		self.status = "Draft"
		for fieldname in STATUS_FIELDS[1:]:
			self.set(fieldname, None)

	def set_employee(self):
		# An approver may enter the expense of anybody; everybody else claims for themselves.
		if self.employee and is_expense_admin():
			return
		self.employee = frappe.session.user

	def validate(self):
		self.validate_lock()
		if not self.is_new() and self.has_value_changed("employee") and not is_expense_admin():
			frappe.throw(_("Only an approver can change the employee of an expense."))
		self.validate_visits()
		self.set_totals()

	def validate_lock(self):
		"""Who may still change the expense, by status."""
		if self.is_new() or self.flags.status_change:
			return
		before = self.get_doc_before_save()
		if not before:
			return
		# The status and approval fields only change through the buttons; keep the stored values.
		for fieldname in STATUS_FIELDS:
			self.set(fieldname, before.get(fieldname))
		if before.status == "Approved":
			frappe.throw(_("Expense {0} is approved and cannot be changed. Unapprove it first.").format(self.name))
		if before.status == "Pending Admin" and not is_expense_admin():
			frappe.throw(_("Expense {0} is waiting for the approver and cannot be changed.").format(self.name))
		if before.status == "Pending Manager":
			frappe.throw(_("Expense {0} is waiting for the manager and cannot be changed.").format(self.name))

	def validate_visits(self):
		"""A visit on a bill must be the employee's own; a bill without a customer gets the visit's customer."""
		for row in self.items:
			if not row.visit:
				continue
			visited_by, customer = frappe.db.get_value("Daily Visit Report", row.visit, ["visited_by", "customer"]) or (None, None)
			if visited_by != self.employee:
				frappe.throw(
					_("Row {0}: visit {1} is not a visit of {2}.").format(row.idx, row.visit, self.employee_name or self.employee)
				)
			if not row.customer and customer:
				row.customer = customer
				row.customer_name = frappe.db.get_value("TP Customer", customer, "customer_name")

	def set_totals(self):
		for row in self.items:
			# The approver may lower the passed amounts at their step; before that a bill is passed in full.
			if self.status in FOLLOW_AMOUNT_STATUSES or row.passed_amount is None:
				row.passed_amount = row.amount
			if flt(row.passed_amount) > flt(row.amount):
				frappe.throw(_("Row {0}: the passed amount cannot be more than the amount of the bill.").format(row.idx))
		self.total_amount = sum(flt(row.amount) for row in self.items)
		self.passed_amount = sum(flt(row.passed_amount) for row in self.items)

	def on_trash(self):
		if self.status == "Approved":
			frappe.throw(_("Expense {0} is approved and cannot be deleted. Unapprove it first.").format(self.name))
		if self.status != "Draft" and not is_expense_admin():
			frappe.throw(_("Expense {0} has been sent for approval and cannot be deleted.").format(self.name))

	def get_reporting_manager(self):
		"""The user the employee reports to, or None (the expense then goes straight to the approver)."""
		manager = frappe.db.get_value("TP Team Member", {"user": self.employee, "inactive": 0}, "reports_to")
		if not manager or manager == self.employee:
			return None
		# A disabled manager could never approve, and the expense would wait for ever.
		if not frappe.db.get_value("User", manager, "enabled"):
			return None
		return manager

	def allowed_actions(self):
		"""Approval steps the logged-in user may take on this expense now."""
		if self.is_new():
			return []
		admin = is_expense_admin()
		user = frappe.session.user
		actions = []
		if self.status == "Draft" and (admin or user == self.employee):
			actions.append("send_for_approval")
		if self.status == "Pending Manager":
			if user == self.get_reporting_manager():
				actions += ["approve", "reject"]
			elif admin:
				# The manager step cannot be skipped; an approver may only send it back.
				actions.append("reject")
		if self.status == "Pending Admin" and admin:
			actions += ["approve", "reject"]
		if self.status == "Approved" and admin:
			actions.append("unapprove")
		return actions

	def check_action(self, action):
		if action not in self.allowed_actions():
			frappe.throw(
				_("You cannot {0} expense {1} while its status is {2}.").format(
					_(action.replace("_", " ")), self.name, _(self.status)
				),
				frappe.PermissionError,
			)

	@frappe.whitelist()
	def send_for_approval(self):
		self.check_action("send_for_approval")
		if not self.items:
			frappe.throw(_("Add at least one bill before sending the expense for approval."))
		self.status = "Pending Manager" if self.get_reporting_manager() else "Pending Admin"
		self.rejection_reason = None
		self.sent_on = now_datetime()
		self.save_status()
		waiting_for = get_fullname(self.get_reporting_manager()) if self.status == "Pending Manager" else _("the approver")
		self.notify(
			_("{0} sent expense {1} ({2}) for approval. Waiting for {3}.").format(
				self.employee_name, self.name, self.get_formatted("total_amount"), waiting_for
			)
		)

	@frappe.whitelist()
	def approve(self):
		self.check_action("approve")
		if self.status == "Pending Manager":
			self.status = "Pending Admin"
			self.approved_by = frappe.session.user
			self.approved_on = now_datetime()
			message = _("{0} approved expense {1} of {2} ({3}). Waiting for the approver.").format(
				get_fullname(), self.name, self.employee_name, self.get_formatted("total_amount")
			)
		else:
			self.status = "Approved"
			self.authorized_by = frappe.session.user
			self.authorized_on = now_datetime()
			message = _("Expense {0} of {1} is approved by {2}: {3} passed of {4}.").format(
				self.name, self.employee_name, get_fullname(), self.get_formatted("passed_amount"), self.get_formatted("total_amount")
			)
		self.save_status()
		self.notify(message)

	@frappe.whitelist()
	def reject(self, reason=None):
		self.check_action("reject")
		reason = cstr(reason).strip()
		if not reason:
			frappe.throw(_("Give the reason for the rejection."))
		# Back to the employee; earlier approvals no longer count.
		self.status = "Draft"
		self.approved_by = self.approved_on = self.authorized_by = self.authorized_on = None
		self.rejection_reason = _("Rejected by {0}: {1}").format(get_fullname(), reason)
		self.save_status()
		self.notify(_("{0} rejected expense {1} of {2}: {3}").format(get_fullname(), self.name, self.employee_name, reason))

	@frappe.whitelist()
	def unapprove(self):
		self.check_action("unapprove")
		self.status = "Pending Admin"
		self.authorized_by = self.authorized_on = None
		self.save_status()
		self.notify(
			_("{0} took back the approval of expense {1} of {2}. Waiting for the approver again.").format(
				get_fullname(), self.name, self.employee_name
			)
		)

	def save_status(self):
		# check_action decided who may do it; a manager has no write permission on a team member's expense.
		self.flags.status_change = True
		self.save(ignore_permissions=True)

	def notify(self, subject):
		"""Bell notification (and email, when the user has it on) to the employee, their manager and the
		approvers. The user who acted gets none."""
		users = {self.employee, self.get_reporting_manager(), *get_approver_users()}
		users -= {None, frappe.session.user, "Administrator"}
		if not users:
			return
		enqueue_create_notification(
			list(users),
			{
				"type": "Alert",
				"document_type": self.doctype,
				"document_name": self.name,
				"subject": subject,
				"from_user": frappe.session.user,
			},
		)


def financial_year(date):
	"""April to March as four digits: 2627 for April 2026 to March 2027."""
	date = getdate(date)
	start = date.year if date.month >= FINANCIAL_YEAR_START else date.year - 1
	return f"{start % 100:02d}{(start + 1) % 100:02d}"


def get_approver_users():
	holders = frappe.get_all("Has Role", filters={"role": APPROVER_ROLE, "parenttype": "User"}, pluck="parent")
	if not holders:
		return set()
	return set(frappe.get_all("User", filters={"name": ["in", holders], "enabled": 1}, pluck="name")) - {"Administrator"}


def expense_report_conditions(filters, alias="e"):
	"""WHERE clause of the expense reports and dashboard: period, employee, status, and only the
	employees the user may see. Returns (sql, values) for `tabTP Expense` written as `alias`."""
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Select a From Date and a To Date."))
	conditions = [f"{alias}.entry_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.get("from_date"), "to_date": filters.get("to_date")}
	if filters.get("employee"):
		conditions.append(f"{alias}.employee = %(employee)s")
		values["employee"] = filters.get("employee")
	if filters.get("status"):
		conditions.append(f"{alias}.status = %(status)s")
		values["status"] = filters.get("status")
	team = get_visible_users()
	if team is not None:
		conditions.append(f"{alias}.employee in {sql_list(team)}")
	return " and ".join(conditions), values


@frappe.whitelist(methods=["POST"])
def bulk_action(names, action):
	"""Run `action` on every expense in `names`; returns how many worked and why the others did not."""
	if action not in BULK_ACTIONS:
		frappe.throw(_("Unknown action {0}").format(action))
	done, failed = 0, []
	for name in frappe.parse_json(names):
		if not frappe.has_permission("TP Expense", "read", name):
			failed.append(_("{0}: not permitted").format(name))
			continue
		try:
			getattr(frappe.get_doc("TP Expense", name), action)()
			done += 1
		except (frappe.ValidationError, frappe.PermissionError) as error:
			failed.append(f"{name}: {error}")
	# The reasons are returned in one list, so drop the separate pop-ups of the failed expenses.
	frappe.clear_messages()
	return {"done": done, "failed": failed}


@frappe.whitelist()
def get_approvals(view="pending"):
	"""Expenses with their bills for the Expense Approvals page: "pending" = waiting for the user's
	approval, "history" = the team's other sent expenses. The user's own expenses are not shown."""
	admin = is_expense_admin()
	user = frappe.session.user
	if admin:
		filters = {"employee": ["!=", user]}
	else:
		members = get_team(user)[1:]
		if not members:
			return {"is_approver": False, "expenses": []}
		filters = {"employee": ["in", members]}
	if view == "pending":
		filters["status"] = ["in", ["Pending Manager", "Pending Admin"]] if admin else "Pending Manager"
	else:
		# Drafts are still the employee's business.
		filters["status"] = ["!=", "Draft"]
	expenses = frappe.get_all(
		"TP Expense",
		filters=filters,
		fields=["name", "entry_date", "employee", "employee_name", "status", "total_amount", "passed_amount", "remark", "approved_by", "approved_on"],
		order_by="entry_date desc, name desc",
		limit_page_length=0 if view == "pending" else HISTORY_LIMIT,
	)
	for expense in expenses:
		# allowed_actions decides, so the page shows exactly the buttons the form would show
		expense.actions = frappe.get_doc("TP Expense", expense.name).allowed_actions() if view == "pending" else []
		if expense.approved_by:
			expense.approved_by_name = get_fullname(expense.approved_by)
	if view == "pending":
		expenses = [expense for expense in expenses if "approve" in expense.actions]
	add_bills(expenses)
	return {"is_approver": True, "is_admin": admin, "expenses": expenses}


def add_bills(expenses):
	if not expenses:
		return
	bills = frappe.get_all(
		"TP Expense Item",
		filters={"parenttype": "TP Expense", "parent": ["in", [expense.name for expense in expenses]]},
		fields=["parent", "idx", "expense_date", "expense_type", "visit", "customer_name", "bill_no", "amount",
			"passed_amount", "description", "bill", "other_attachment"],
		order_by="parent, idx",
	)
	by_expense = {}
	for bill in bills:
		by_expense.setdefault(bill.parent, []).append(bill)
	for expense in expenses:
		expense.bills = by_expense.get(expense.name, [])


@frappe.whitelist()
def get_visit_expenses(visit):
	"""Claims and amount spent on one visit, for the Expense card on the DVR form."""
	frappe.has_permission("Daily Visit Report", "read", visit, throw=True)
	rows = frappe.db.sql(
		"""
		select count(distinct e.name) as claims, ifnull(sum(i.amount), 0) as amount
		from `tabTP Expense Item` i
		join `tabTP Expense` e on e.name = i.parent and i.parenttype = 'TP Expense'
		where i.visit = %s
		""",
		visit,
		as_dict=True,
	)
	return rows[0]
