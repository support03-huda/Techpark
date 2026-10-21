# Copyright (c) 2026, Techpark International
"""Competitor brands seen on customer lines. Not called "Competitor": ERPNext has a DocType with that name."""

from frappe.model.document import Document


class TPCompetitor(Document):
	def validate(self):
		self.competitor_name = (self.competitor_name or "").strip()
