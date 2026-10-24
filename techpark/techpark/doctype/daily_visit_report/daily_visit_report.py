# Copyright (c) 2026, Techpark International
"""Daily Visit Report (DVR) — one record per customer visit.

Captures the visit once; demand records are created from it, and
the next action becomes a ToDo for the employee so the follow-up is tracked.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from techpark.permission import is_locked, is_manager

DISTRIBUTOR = "TP"

# Lead stage -> % of the sales cycle completed. Keep in sync with daily_visit_report.js.
STAGE_PROGRESS = {
	"Introduction": 10,
	"Received Enquiry": 25,
	"Requirement Shared": 40,
	"Technical Discussion": 50,
	"Trial / Sample": 60,
	"Quotation Submitted": 75,
	"Negotiation": 90,
	"Order Received": 100,
}


def contact_label(contact):
	"""How a contact is shown on the customer's Visits tab: "Name (Designation)"."""
	return f"{contact.person_name} ({contact.designation})" if contact.designation else contact.person_name


def find_contact(customer, label):
	"""Customer Contact of this customer whose name or "Name (Designation)" is `label`."""
	label = (label or "").strip()
	contacts = frappe.get_all(
		"Customer Contact",
		filters={"customer": customer},
		fields=["name", "person_name", "designation"],
		order_by="is_active desc, is_primary desc, creation",
	)
	for contact in contacts:
		if label in (contact_label(contact), contact.person_name):
			return contact.name
	return None


class DailyVisitReport(Document):
	def onload(self):
		self.set_onload("locked", is_locked(self))

	def validate(self):
		self.distributor = DISTRIBUTOR
		self.validate_visited_by()
		self.validate_dates()
		self.validate_plant()
		self.set_contact()
		self.validate_segment()
		self.validate_supplier_product_category()
		self.set_stage_completed()

	def set_contact(self):
		"""Contact Person links the Customer Contact; Contact Person Name (also set from the
		customer's Visits tab) is kept in step with it."""
		# has_value_changed() is always true on a new visit, so only an existing one can be "cleared".
		existing = not self.is_new()
		if existing and self.has_value_changed("contact") and not self.contact:
			self.contact_person = None
		elif not self.contact or (
			existing and not self.has_value_changed("contact") and self.has_value_changed("contact_person")
		):
			self.contact = find_contact(self.customer, self.contact_person) if self.contact_person else None

		if not self.contact:
			self.contact_designation = self.contact_phone = None
			return
		contact = frappe.db.get_value(
			"Customer Contact", self.contact, ["customer", "person_name", "designation", "phone"], as_dict=True
		)
		if contact.customer != self.customer:
			frappe.throw(
				_("Contact {0} does not belong to customer {1}.").format(
					frappe.bold(contact.person_name), frappe.bold(self.customer_name or self.customer)
				)
			)
		self.contact_person = contact_label(contact)
		self.contact_designation = contact.designation
		self.contact_phone = contact.phone

	def validate_visited_by(self):
		"""A Sales User files visits only for themselves; managers may pick anyone."""
		if is_manager():
			return
		if self.is_new():
			self.visited_by = frappe.session.user
		elif self.has_value_changed("visited_by"):
			frappe.throw(_("Only a manager can change the Employee of a visit."))

	def validate_dates(self):
		if getdate(self.visit_date) > getdate(today()):
			frappe.throw(_("Visit Date cannot be in the future."))
		if self.next_action_date and getdate(self.next_action_date) < getdate(self.visit_date):
			frappe.throw(_("Next Action By cannot be before the Visit Date."))

	def validate_plant(self):
		plant_customer = frappe.db.get_value("Plant", self.plant, "customer")
		if plant_customer != self.customer:
			frappe.throw(
				_("Plant {0} does not belong to customer {1}.").format(
					frappe.bold(self.plant_name or self.plant), frappe.bold(self.customer_name or self.customer)
				)
			)

	def validate_segment(self):
		if not self.segment_application:
			return
		segment_customer = frappe.db.get_value("Customer Segment Application", self.segment_application, "customer")
		if segment_customer != self.customer:
			frappe.throw(
				_("Segment / Line {0} does not belong to customer {1}.").format(
					frappe.bold(self.segment_application), frappe.bold(self.customer_name or self.customer)
				)
			)

	def validate_supplier_product_category(self):
		if not self.supplier_product_category:
			return
		category_principal = frappe.db.get_value(
			"Supplier Product Category", self.supplier_product_category, "principal"
		)
		if category_principal != self.principal:
			frappe.throw(
				_("Supplier Product Category {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.supplier_product_category),
					frappe.bold(category_principal),
					frappe.bold(self.principal or _("no principal")),
				)
			)

	def set_stage_completed(self):
		if self.lead_status == "Won":
			self.lead_stage = "Order Received"
		self.stage_completed = STAGE_PROGRESS.get(self.lead_stage, 0)

	def on_submit(self):
		self.create_follow_up()
		self.activate_customer()
		self.add_principal_to_customer()

	# Lead Status / Lead Stage are "Allow on Submit": the lead can move forward on a
	# submitted visit. Frappe skips validate() for these updates, so recompute here.
	def before_update_after_submit(self):
		self.set_stage_completed()

	def on_update_after_submit(self):
		self.activate_customer()

	def on_cancel(self):
		if self.follow_up and frappe.db.get_value("ToDo", self.follow_up, "status") == "Open":
			frappe.db.set_value("ToDo", self.follow_up, "status", "Cancelled")

	def create_follow_up(self):
		if not self.next_action:
			return
		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": self.visited_by,
				"date": self.next_action_date,
				"description": _("{0} — {1}").format(self.customer_name, self.next_action),
				"reference_type": self.doctype,
				"reference_name": self.name,
				"assigned_by": frappe.session.user,
			}
		).insert(ignore_permissions=True)
		self.db_set("follow_up", todo.name)

	def activate_customer(self):
		"""A won visit turns a Prospect into an Active Customer."""
		if self.lead_status != "Won":
			return
		if frappe.db.get_value("TP Customer", self.customer, "customer_status") == "Prospect":
			frappe.db.set_value("TP Customer", self.customer, "customer_status", "Active Customer")
			frappe.get_doc("TP Customer", self.customer).add_comment(
				"Info", _("Marked Active Customer from won visit {0}").format(self.name)
			)

	def add_principal_to_customer(self):
		"""Keep the customer's Principals list (principal-wise customer list) in step with its visits."""
		if not self.principal:
			return
		filters = {"parenttype": "TP Customer", "parentfield": "principals", "parent": self.customer}
		if frappe.db.exists("Customer Principal", {**filters, "principal": self.principal}):
			return
		frappe.get_doc(
			{
				"doctype": "Customer Principal",
				**filters,
				"principal": self.principal,
				"idx": frappe.db.count("Customer Principal", filters) + 1,
			}
		).db_insert()
