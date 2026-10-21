# Copyright (c) 2026, Techpark International
"""Abrasive / Wheel Consumption — code 701, 702 … as per the approved client spec."""

from frappe.model.document import Document

from techpark.naming import next_numeric_name

CONSUMPTION_CODE_START = 701


class WheelConsumption(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, CONSUMPTION_CODE_START)
