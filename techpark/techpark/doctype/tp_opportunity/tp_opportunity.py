# Copyright (c) 2026, Techpark International
"""One development / opportunity: a customer's application line with a principal (and product category /
wheel spec), followed from introduction to regularisation. Its status comes from the visits
(techpark/opportunity.py); importance, notes and reasons are entered here."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class TPOpportunity(Document):
	def validate(self):
		for field in ("application", "spec", "size"):
			self.set(field, (self.get(field) or "").strip() or None)
		self.title = " · ".join(p for p in (self.customer_name, self.application, self.principal, self.spec) if p)
		self.check_key_unchanged()
		self.check_duplicate()

	def check_key_unchanged(self):
		"""Product Category and Spec identify the line, like customer / application / principal
		(those are Set Only Once). Compared as text: an empty value saved as NULL, or a numbered
		(autoincrement) category read back as text, is not a change."""
		before = self.get_doc_before_save()
		if not before:
			return
		for field in ("supplier_product_category", "spec"):
			if cstr(before.get(field)).strip() != cstr(self.get(field)).strip():
				frappe.throw(
					_("{0} cannot be changed: it identifies this application line.").format(
						_(self.meta.get_label(field))
					)
				)

	def check_duplicate(self):
		other = frappe.db.sql(
			"""select name from `tabTP Opportunity`
			where customer = %s and application = %s and principal = %s
				and ifnull(supplier_product_category, '') = %s and ifnull(spec, '') = %s and name != %s
			limit 1""",
			(self.customer, self.application, self.principal, cstr(self.supplier_product_category), cstr(self.spec), self.name or ""),
		)
		if other:
			frappe.throw(
				_("This application line is already followed as {0}.").format(
					frappe.get_desk_link("TP Opportunity", other[0][0])
				),
				frappe.DuplicateEntryError,
			)
