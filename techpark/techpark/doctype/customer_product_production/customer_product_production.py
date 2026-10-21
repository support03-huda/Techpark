# Copyright (c) 2026, Techpark International
"""Customer Product & Production — code 301, 302 … as per the approved client spec."""

from frappe.model.document import Document

from techpark.naming import next_numeric_name

PRODUCTION_CODE_START = 301


class CustomerProductProduction(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, PRODUCTION_CODE_START)
