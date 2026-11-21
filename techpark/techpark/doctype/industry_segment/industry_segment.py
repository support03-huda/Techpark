# Copyright (c) 2026, Techpark International
"""Industry Segment: Bearing, Steel, … (Customer, Product and Application)."""

from frappe.model.document import Document


class IndustrySegment(Document):
	def validate(self):
		self.industry_name = (self.industry_name or "").strip()
