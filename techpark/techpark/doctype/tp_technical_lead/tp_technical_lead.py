# Copyright (c) 2026, Techpark International
"""One application of a customer (Demand Survey row). Filled once, then picked on visits."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class TPTechnicalLead(Document):
	def validate(self):
		if self.application_master:
			# Common application list: the name (and defaults) come from the master
			master = frappe.db.get_value(
				"Customer Application", self.application_master, ["application_name", "grinding_process", "product", "supplier_product_category", "principal", "production_line"],
				as_dict=True,
			)
			if master:
				self.application = master.application_name
				self.grinding_process = master.grinding_process
				self.product = self.product or master.product
				self.production_line = self.production_line or master.production_line
				if not self.supplier_product_category and master.supplier_product_category and master.principal == self.principal:
					self.supplier_product_category = master.supplier_product_category
		self.application = cstr(self.application).strip()
		if not self.application:
			frappe.throw(_("Pick the Application."))
		if self.supplier_product_category and self.principal:
			principal = frappe.db.get_value("Supplier Product Category", self.supplier_product_category, "principal")
			if principal and principal != self.principal:
				frappe.throw(_("Principal Product Category {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.supplier_product_category), principal, self.principal
				))
