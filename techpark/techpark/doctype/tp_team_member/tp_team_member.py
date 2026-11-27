# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""Reporting line: who a user reports to. The person they report to approves their expenses first.
2026-11-26: Reports To by Principal: for these principals the work (customers, visits, lines) goes to another manager,
e.g. Shiv's Noritake customers -> Santosh, his Everloy customers -> Abhijeet. Reports To covers the rest."""

import frappe
from frappe import _
from frappe.model.document import Document


class TPTeamMember(Document):
	def validate(self):
		if self.reports_to and self.reports_to == self.user:
			frappe.throw(_("A person cannot report to themselves."))
		# 2026-11-26
		seen = set()
		for row in self.get("principal_reporting") or []:
			if row.reports_to == self.user:
				frappe.throw(_("Row {0}: a person cannot report to themselves.").format(row.idx))
			if row.principal in seen:
				frappe.throw(_("Row {0}: {1} is entered twice.").format(row.idx, frappe.bold(row.principal)))
			seen.add(row.principal)
