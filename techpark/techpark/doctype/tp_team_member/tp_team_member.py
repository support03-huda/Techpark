# Copyright (c) 2026, Techpark International
"""Reporting line: who a user reports to. The person they report to approves their expenses first."""

import frappe
from frappe import _
from frappe.model.document import Document


class TPTeamMember(Document):
	def validate(self):
		if self.reports_to and self.reports_to == self.user:
			frappe.throw(_("A person cannot report to themselves."))
