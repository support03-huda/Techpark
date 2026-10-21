# Copyright (c) 2026, Techpark International
"""Manufacturing Details — code 901, 902 … as per the approved client spec."""

from frappe.model.document import Document

from techpark.naming import next_numeric_name

MANUFACTURING_CODE_START = 901


class ManufacturingDetails(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, MANUFACTURING_CODE_START)
