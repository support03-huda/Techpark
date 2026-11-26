# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""One application of a customer (Demand Survey row). Filled once, then picked on visits."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from techpark.shares import validate_shares


class TPTechnicalLead(Document):
	# 2026-11-26: leads can be made by hand (form / customer tab) and from a DVR (client: keep it flexible);
	# check_duplicate stops a second lead for the same application + production line either way.
	def before_insert(self):
		self.lead_created_on = now_datetime()  # 2026-11-26: when the lead was made (client)

	def validate(self):
		self.check_duplicate()  # 2026-11-26
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

	def check_duplicate(self):
		"""2026-11-26: one Technical Lead per customer + principal + application + production line
		(one application can run on several lines: Ch-1, Ch-2 ...)."""
		if not (self.customer and self.principal and self.application_master):
			return
		other = frappe.db.sql(
			"""select name from `tabTP Technical Lead`
			where customer = %s and principal = %s and application_master = %s
				and lower(trim(ifnull(production_line, ''))) = %s and ifnull(product, '') = %s and name != %s limit 1""",
			(
				self.customer, self.principal, self.application_master,
				cstr(self.production_line).strip().lower(), cstr(self.product), self.name or "",
			),  # 2026-11-26: Product is part of the lead too
		)
		if other:
			frappe.throw(
				_("This customer already has this Technical Lead (same application, product and production line): {0}. Open it, or make a DVR for it.").format(
					frappe.get_desk_link("TP Technical Lead", other[0][0])
				),
				frappe.DuplicateEntryError,
			)
