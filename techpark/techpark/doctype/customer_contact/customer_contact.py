# Copyright (c) 2026, Techpark International
"""Customer Contact — a person at a customer (Secondary Contacts Master), code CON-0001 …

Standalone so visits can link to the person met. The customer's
Contacts tab mirrors these records (techpark/customer_sync.py).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import cint, now_datetime, validate_email_address


class CustomerContact(Document):
	def validate(self):
		self.person_name = (self.person_name or "").strip()
		if self.email:
			validate_email_address(self.email, throw=True)
		if not self.is_active:
			self.is_primary = 0
		self.track_inactivation()

	def on_update(self):
		# Saved from the customer's Contacts tab: the customer has already validated
		# the single primary and set its own Contact Name / Phone / Email.
		if frappe.flags.tp_customer_sync:
			return
		if cint(self.is_primary):
			frappe.db.set_value(
				self.doctype,
				{"customer": self.customer, "is_primary": 1, "name": ("!=", self.name)},
				"is_primary",
				0,
			)
		before = self.get_doc_before_save()
		if before and before.customer != self.customer:
			set_customer_primary(before.customer)
		set_customer_primary(self.customer)

	def after_delete(self):
		if not frappe.flags.tp_customer_sync and self.is_primary:
			set_customer_primary(self.customer)

	def track_inactivation(self):
		if self.is_active:
			self.inactivated_by = None
			self.inactivated_on = None
			return
		before = self.get_doc_before_save()
		if not before or before.is_active:
			self.inactivated_by = frappe.session.user
			self.inactivated_on = now_datetime()


def set_customer_primary(customer):
	"""Copy the customer's primary contact into TP Customer's Contact Name / Phone / Email."""
	if not customer or not frappe.db.exists("TP Customer", customer):
		return
	primary = frappe.db.get_value(
		"Customer Contact",
		{"customer": customer, "is_primary": 1, "is_active": 1},
		["person_name", "phone", "email"],
		as_dict=True,
	) or {}
	frappe.db.set_value(
		"TP Customer",
		customer,
		{
			"primary_contact_name": primary.get("person_name"),
			"primary_contact_phone": primary.get("phone"),
			"primary_contact_email": primary.get("email"),
		},
		update_modified=False,
	)
