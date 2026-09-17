# Copyright (c) 2026, Techpark International
"""Plant Master — code 101, 102 … linked to a Customer."""

import re

import frappe
from frappe import _
from frappe.model.document import Document

from techpark.naming import next_numeric_name

PLANT_CODE_START = 101


class Plant(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, PLANT_CODE_START)

	def validate(self):
		self.plant_name = (self.plant_name or "").strip()
		if self.pincode and (self.country or "India") == "India" and not re.fullmatch(r"\d{6}", self.pincode.strip()):
			frappe.throw(_("Pincode must be 6 digits."))
		duplicate = frappe.db.get_value(
			self.doctype,
			{"customer": self.customer, "plant_name": self.plant_name, "name": ("!=", self.name or "")},
			"name",
		)
		if duplicate:
			frappe.throw(_("This customer already has a plant named {0} ({1}).").format(
				frappe.bold(self.plant_name), duplicate
			))
