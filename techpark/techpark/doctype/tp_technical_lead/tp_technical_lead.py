# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
"""One application of a customer (Demand Survey row). Filled once, then picked on visits."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr

from techpark.shares import validate_shares


class TPTechnicalLead(Document):
	def validate(self):
		if self.application_master:
			# Common application list: the name (and defaults) come from the master
			master = frappe.db.get_value(
				"Customer Application", self.application_master, ["application_name", "grinding_process", "product"],
				as_dict=True,
			)
			if master:
				self.application = master.application_name
				self.grinding_process = master.grinding_process
				self.product = self.product or master.product
				# 2026-11-21: category / line no longer on the Application master (client)
		validate_shares(self)  # 2026-11-21: Principal + 4 competitors, max 100%
		self.application = cstr(self.application).strip()
		if not self.application:
			frappe.throw(_("Pick the Application."))
		if self.supplier_product_category and self.principal:
			principal = frappe.db.get_value("Supplier Product Category", self.supplier_product_category, "principal")
			if principal and principal != self.principal:
				frappe.throw(_("Principal Product Category {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.supplier_product_category), principal, self.principal
				))
