# Copyright (c) 2026, Techpark International
"""Pending Work reminders (TechPark Settings > Pending Work Reminders, on by default).

Daily 09:00 - each responsible person: their work due tomorrow, due today and overdue.
            - admins / approvers: everything overdue.
Monday      - admins / approvers: all open pending work by person.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, formatdate, getdate, today

from techpark.reminders import add, deliver, link

OPEN = ("Open", "In Progress")
ADMIN_ROLES = ("System Manager", "TechPark Approver")


def _open_work():
	work = frappe.get_all(
		"TP Pending Work",
		filters={"status": ("in", OPEN)},
		fields=["name", "task", "category", "customer_name", "due_date", "priority", "status", "responsible_names"],
		order_by="due_date asc",
	)
	people = defaultdict(list)
	for r in frappe.get_all(
		"TP Pending Work User", filters={"parenttype": "TP Pending Work", "parent": ("in", [w.name for w in work] or [""])},
		fields=["parent", "user"],
	):
		people[r.parent].append(r.user)
	return work, people


def _admins():
	users = frappe.get_all("Has Role", filters={"parenttype": "User", "role": ("in", ADMIN_ROLES)}, pluck="parent", distinct=True)
	return [u for u in users if u not in ("Administrator", "Guest")]


def _row(w, now):
	if not w.due_date:
		when = _("No due date")
	else:
		late = date_diff(now, w.due_date)
		when = (
			_("{0} days late").format(late) if late > 0
			else _("Today") if late == 0
			else _("Tomorrow") if late == -1
			else _("in {0} days").format(-late)
		)
	return [
		link("tp-pending-work", w.name, w.task), w.category or "", w.customer_name or "",
		formatdate(w.due_date) if w.due_date else "", when, w.priority or "", w.responsible_names or "",
	]


COLS = [_("Pending Work"), _("Category"), _("Customer"), _("Due"), _("When"), _("Priority"), _("Responsible")]


def daily(dry_run=False):
	now = getdate(today())
	work, people = _open_work()
	digests = defaultdict(list)
	mine = defaultdict(list)
	for w in work:
		if w.due_date and getdate(w.due_date) <= add_days(now, 1):
			for user in people[w.name]:
				mine[user].append(w)
	for user, items in mine.items():
		add(digests, [user], _("Your pending work"), COLS, [_row(w, now) for w in items])
	overdue = [w for w in work if w.due_date and getdate(w.due_date) < now]
	add(digests, _admins(), _("Overdue pending work (all)"), COLS, [_row(w, now) for w in overdue])
	return deliver(digests, _("TechPark: pending work due"), "/app/tp-pending-work", dry_run, setting="pending_work_reminders")


def weekly(dry_run=False):
	now = getdate(today())
	work, _people = _open_work()
	digests = defaultdict(list)
	add(digests, _admins(), _("All open pending work"), COLS, [_row(w, now) for w in work])
	return deliver(digests, _("TechPark weekly: open pending work"), "/app/tp-pending-work", dry_run, setting="pending_work_reminders")


def preview(job="daily"):
	result = {"daily": daily, "weekly": weekly}[job](dry_run=True)
	for user, sections in result.items():
		print(user, {title: len(rows) for title, _cols, rows in sections})
	if not result:
		print("Nothing to send.")
