# Copyright (c) 2026, Techpark International
"""Visit Expense — travel/food/lodging spent on a customer visit, linked to its DVR."""

import frappe
from frappe import _
from frappe.model.document import Document


class VisitExpense(Document):
	def validate(self):
		if (self.amount or 0) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if frappe.db.get_value("Daily Visit Report", self.daily_visit_report, "docstatus") == 2:
			frappe.throw(_("Daily Visit Report {0} is cancelled.").format(self.daily_visit_report))
