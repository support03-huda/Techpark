# Copyright (c) 2026, Techpark International
"""One application of a customer (Demand Survey row). Filled once, then picked on visits."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class TPTechnicalLead(Document):
	def validate(self):
		self.application = cstr(self.application).strip()
		if self.supplier_product_category and self.principal:
			principal = frappe.db.get_value("Supplier Product Category", self.supplier_product_category, "principal")
			if principal and principal != self.principal:
				frappe.throw(_("Principal Product Category {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.supplier_product_category), principal, self.principal
				))
