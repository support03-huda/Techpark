# Copyright (c) 2026, Techpark International
"""Wheel Specification — code 801, 802 … as per the approved client spec."""

from frappe.model.document import Document

from techpark.naming import next_numeric_name

WHEEL_CODE_START = 801


class WheelSpecification(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, WHEEL_CODE_START)
