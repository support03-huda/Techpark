# Last edited: 2026-11-14
# Copyright (c) 2026, Techpark International
"""Pending Work: a task with its responsible people and due date (the sheet they kept in Teams).
Each responsible person gets it assigned (their ToDo list) and a daily reminder (techpark.pending_work)."""

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import get_fullname, today

CLOSED = ("Done", "Cancelled")


class TPPendingWork(Document):
	def validate(self):
		seen = set()
		self.responsible = [r for r in self.responsible if r.user and not (r.user in seen or seen.add(r.user))]
		if not self.responsible:
			# nobody picked: the person entering it
			self.append("responsible", {"user": frappe.session.user})
		self.responsible_names = ", ".join(get_fullname(r.user) for r in self.responsible)
		if self.status == "Done" and not self.completed_on:
			self.completed_on = today()
		elif self.status != "Done":
			self.completed_on = None

	def on_update(self):
		self.sync_assignments()

	def on_trash(self):
		assign_to.clear(self.doctype, self.name, ignore_permissions=True)

	def sync_assignments(self):
		"""Responsible people = open assignments; closed work closes them."""
		users = {r.user for r in self.responsible}
		open_todos = frappe.get_all(
			"ToDo",
			filters={"reference_type": self.doctype, "reference_name": self.name, "status": "Open"},
			fields=["name", "allocated_to"],
		)
		assigned = {t.allocated_to for t in open_todos}
		for t in open_todos:
			if self.status in CLOSED or t.allocated_to not in users:
				todo = frappe.get_doc("ToDo", t.name)
				todo.status = "Closed" if self.status == "Done" else "Cancelled"
				todo.save(ignore_permissions=True)  # also updates the "assigned to" markers
		if self.status in CLOSED:
			return
		new = sorted(users - assigned)
		if new:
			# Frappe 16: add() always checks the current user's permission; _add() can skip it
			add = getattr(assign_to, "_add", None) or (lambda args, **kw: assign_to.add(args))
			add(
				{
					"doctype": self.doctype,
					"name": self.name,
					"assign_to": new,
					"date": self.due_date,
					"priority": self.priority,
					"description": self.task,
				},
				ignore_permissions=True,
			)
		# keep the due date / priority of open assignments in step
		for t in open_todos:
			if t.allocated_to in users:
				frappe.db.set_value("ToDo", t.name, {"date": self.due_date, "priority": self.priority, "description": self.task})
