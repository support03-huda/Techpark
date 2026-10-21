# Copyright (c) 2026, Techpark International
"""Customer Master — code 10001, 10002 … as per the approved client spec."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, now_datetime, today, validate_email_address

from techpark.customer_sync import push_to_records
from techpark.naming import next_numeric_name

CUSTOMER_CODE_START = 10001


class TPCustomer(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, CUSTOMER_CODE_START)
		self.customer_code = self.name

	def validate(self):
		self.customer_name = (self.customer_name or "").strip()
		self.customer_code = self.name
		self.validate_duplicate_name()
		self.validate_established_year()
		self.remove_duplicate_principals()
		self.validate_contacts()
		self.track_inactivation()
		self.track_prospect()

	def on_update(self):
		# Contacts / Plants / Production / Commercial / Visits tab rows -> real records
		push_to_records(self)

	def validate_duplicate_name(self):
		duplicate = frappe.db.get_value(
			self.doctype,
			{"customer_name": self.customer_name, "name": ("!=", self.name or "")},
			"name",
		)
		if duplicate:
			frappe.throw(
				_("Customer {0} already exists with code {1}.").format(
					frappe.bold(self.customer_name), frappe.bold(duplicate)
				),
				title=_("Duplicate Customer"),
			)

	def validate_established_year(self):
		if self.established_year and not (1800 <= cint(self.established_year) <= getdate().year):
			frappe.throw(_("Established (Year) must be a year between 1800 and {0}.").format(getdate().year))

	def remove_duplicate_principals(self):
		seen = set()
		for row in list(self.get("principals") or []):
			if row.principal in seen:
				self.remove(row)
			seen.add(row.principal)

	def validate_contacts(self):
		primaries = []
		for row in self.get("contacts") or []:
			if row.get("email"):
				validate_email_address(row.email, throw=True)
			if not cint(row.get("is_active")):
				row.is_primary = 0
			if cint(row.get("is_primary")):
				primaries.append(row)

		if len(primaries) > 1:
			frappe.throw(_("Only one contact can be marked as Primary."))

		if primaries:
			primary = primaries[0]
			self.primary_contact_name = primary.get("person_name")
			self.primary_contact_phone = primary.get("phone")
			self.primary_contact_email = primary.get("email")

	def track_inactivation(self):
		if self.customer_status != "Inactive":
			self.inactivated_by = None
			self.inactivated_on = None
			return

		before = self.get_doc_before_save()
		if not before or before.customer_status != "Inactive":
			self.inactivated_by = frappe.session.user
			self.inactivated_on = now_datetime()

	def track_prospect(self):
		"""Start the prospect clock when the status becomes Prospect (used by the 7-day Prospect notification)."""
		if self.customer_status != "Prospect":
			self.prospect_since = None
			return

		before = self.get_doc_before_save()
		if not before or before.customer_status != "Prospect":
			self.prospect_since = today()
