# Copyright (c) 2026, Techpark International
"""Industry Domain — the industry dropdown on the Customer Master."""

from frappe.model.document import Document


class IndustryDomain(Document):
	def validate(self):
		self.industry_name = (self.industry_name or "").strip()
