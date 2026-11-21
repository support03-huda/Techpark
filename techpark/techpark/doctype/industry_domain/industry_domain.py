# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Industry Domain is back as its own master, used only in Customer Details (client)
"""Industry Domain of a customer (Customer Details only). Products / applications use Industry/Product Segment."""

from frappe.model.document import Document


class IndustryDomain(Document):
	def validate(self):
		self.industry_name = (self.industry_name or "").strip()
