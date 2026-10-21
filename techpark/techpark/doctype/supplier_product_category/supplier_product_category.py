# Copyright (c) 2026, Techpark International
"""Supplier Product Category — what a Principal supplies (Super Abrasive, Dresser, …)."""

import frappe
from frappe import _
from frappe.model.document import Document


class SupplierProductCategory(Document):
	def validate(self):
		self.category_name = (self.category_name or "").strip()
		duplicate = frappe.db.get_value(
			self.doctype,
			{"principal": self.principal, "category_name": self.category_name, "name": ("!=", self.name or 0)},
		)
		if duplicate:
			frappe.throw(
				_("{0} already has the category {1}.").format(
					frappe.bold(self.principal), frappe.bold(self.category_name)
				)
			)
