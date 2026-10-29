# Copyright (c) 2026, Techpark International
"""Daily Visit Report (DVR) — one record per customer visit, call or meeting.

Captures the visit once; demand records are created from it, and
the next action becomes a ToDo for the employee so the follow-up is tracked.

Principal-wise: every principal discussed is a row (DVR Principal) with two stages.
Development (introduction ... Successful Trial) comes first; the Sales stage (quotation ...
Order Won / Regularization) opens only once the trial was successful for that customer,
principal and product category, on this visit or an earlier submitted one. The old single
fields (principal, lead status / stage, stage completed) are kept as a summary of the rows.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from techpark.permission import is_locked, is_manager

DISTRIBUTOR = "TP"

# Status -> % of the whole cycle (Development up to 50%, Sales after). Keep in sync with daily_visit_report.js.
DEVELOPMENT_PROGRESS = {
	"Introduction": 10,
	"Requirement Shared": 20,
	"Sample / Trial Planned": 30,
	"Trial in Progress": 40,
	"Successful Trial": 50,
	"Trial Failed": 40,
}
SALES_PROGRESS = {
	"Quotation Submitted": 65,
	"Negotiation": 80,
	"Order Won": 100,
	"Regularization": 100,
	"Order Lost": 50,
	"On Hold": 50,
}
STAGE_PROGRESS = {**DEVELOPMENT_PROGRESS, **SALES_PROGRESS}
TRIAL_DONE = "Successful Trial"
WON_STATUSES = ("Order Won", "Regularization")
LOST_STATUSES = ("Order Lost", "Trial Failed")

# Old single Lead Stage / Status -> (stage, development status, sales status) of a principal row.
OLD_STAGES = {
	"Introduction": ("Development", "Introduction", None),
	"Received Enquiry": ("Development", "Requirement Shared", None),
	"Requirement Shared": ("Development", "Requirement Shared", None),
	"Technical Discussion": ("Development", "Requirement Shared", None),
	"Trial / Sample": ("Development", "Trial in Progress", None),
	"Quotation Submitted": ("Sales", TRIAL_DONE, "Quotation Submitted"),
	"Negotiation": ("Sales", TRIAL_DONE, "Negotiation"),
	"Order Received": ("Sales", TRIAL_DONE, "Order Won"),
}


def row_from_lead(lead_stage, lead_status):
	"""Development / Sales status of a principal row for an old-style Lead Stage + Lead Status
	(visits entered on the customer's Visits tab, and visits made before principal rows existed)."""
	if lead_stage in DEVELOPMENT_PROGRESS:
		stage, development, sales = "Development", lead_stage, None
	elif lead_stage in SALES_PROGRESS:
		stage, development, sales = "Sales", TRIAL_DONE, lead_stage
	else:
		stage, development, sales = OLD_STAGES.get(lead_stage, ("Development", "Introduction", None))
	if lead_status == "Won":
		stage, development, sales = "Sales", TRIAL_DONE, "Order Won"
	elif lead_status == "Lost":
		if stage == "Sales":
			sales = "Order Lost"
		else:
			development = "Trial Failed"
	elif lead_status == "On Hold" and stage == "Sales":
		sales = "On Hold"
	return {"stage": stage, "development_status": development, "sales_status": sales}


@frappe.whitelist()
def development_done(customer, principal, supplier_product_category=None, exclude=None):
	"""True when an earlier submitted visit of this customer recorded a successful trial (or already
	reached the Sales stage) for this principal and product category."""
	if not (customer and principal):
		return False
	return bool(
		frappe.db.sql(
			"""
			select 1
			from `tabDVR Principal` r
			join `tabDaily Visit Report` d on d.name = r.parent and r.parenttype = 'Daily Visit Report'
			where d.docstatus = 1 and d.customer = %(customer)s and d.name != %(exclude)s
				and r.principal = %(principal)s and ifnull(r.supplier_product_category, '') = %(category)s
				and (r.development_status = %(done)s or r.stage = 'Sales')
			limit 1
			""",
			{
				"customer": customer,
				"principal": principal,
				"category": supplier_product_category or "",
				"exclude": exclude or "",
				"done": TRIAL_DONE,
			},
		)
	)


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
		self.set_principal_rows()

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

	def set_principal_rows(self):
		"""Stage and progress of every principal row, then the summary fields."""
		self.add_row_from_summary()
		if not self.principals:
			frappe.throw(_("Add at least one Principal discussed on this visit."))
		seen = set()
		for row in self.principals:
			key = (row.principal, row.supplier_product_category or "")
			if key in seen:
				frappe.throw(
					_("Principals row {0}: {1} is entered twice.").format(
						row.idx, " / ".join(p for p in key if p)
					)
				)
			seen.add(key)
			self.validate_category(row)
			self.set_row_stage(row)
		self.set_summary()

	def add_row_from_summary(self):
		"""A new visit entered on the customer's Visits tab has only the single Principal /
		Lead Stage: make it the first row. (Older visits got their rows from the dvr_principal_rows patch.)"""
		if not self.is_new() or self.principals or not self.principal:
			return
		row = self.append(
			"principals",
			{
				"principal": self.principal,
				"supplier_product_category": self.supplier_product_category,
				**row_from_lead(self.lead_stage, self.lead_status),
			},
		)
		# A sales status here cannot skip the Development stage.
		if row.stage == "Sales" and not development_done(
			self.customer, row.principal, row.supplier_product_category, self.name
		):
			frappe.throw(
				_("{0}: {1} needs a Successful Trial first. Record the trial for this principal before the sale.").format(
					frappe.bold(row.principal), frappe.bold(row.sales_status)
				)
			)

	def validate_category(self, row):
		if not row.supplier_product_category:
			return
		category_principal = frappe.db.get_value("Supplier Product Category", row.supplier_product_category, "principal")
		if category_principal != row.principal:
			frappe.throw(
				_("Principals row {0}: Product Category {1} belongs to {2}, not {3}.").format(
					row.idx,
					frappe.bold(row.supplier_product_category),
					frappe.bold(category_principal),
					frappe.bold(row.principal),
				)
			)

	def set_row_stage(self, row):
		row.development_done_before = 1 if development_done(
			self.customer, row.principal, row.supplier_product_category, self.name
		) else 0
		if row.development_done_before:
			row.development_status = TRIAL_DONE
		if not row.development_status:
			frappe.throw(
				_("Principals row {0} ({1}): select the Development Status.").format(row.idx, frappe.bold(row.principal))
			)
		row.stage = "Sales" if row.development_status == TRIAL_DONE else "Development"
		if row.sales_status and row.stage != "Sales":
			frappe.throw(
				_("Principals row {0} ({1}): Sales Status {2} can be set only after a Successful Trial.").format(
					row.idx, frappe.bold(row.principal), frappe.bold(row.sales_status)
				)
			)
		row.progress = STAGE_PROGRESS.get(row.sales_status or row.development_status, 0)

	def set_summary(self):
		"""The single fields other screens read: first principal, the furthest status, overall lead status."""
		rows = self.principals
		self.principal = rows[0].principal
		self.supplier_product_category = rows[0].supplier_product_category
		self.principal_list = ", ".join(dict.fromkeys(row.principal for row in rows))
		furthest = max(rows, key=lambda row: row.progress or 0)
		self.lead_stage = furthest.sales_status or furthest.development_status
		self.stage_completed = furthest.progress or 0
		statuses = [row.sales_status or row.development_status for row in rows]
		if any(s in WON_STATUSES for s in statuses):
			self.lead_status = "Won"
		elif all(s in LOST_STATUSES for s in statuses):
			self.lead_status = "Lost"
		elif all(s == "On Hold" for s in statuses):
			self.lead_status = "On Hold"
		else:
			self.lead_status = "Prospect"

	def on_submit(self):
		self.create_follow_up()
		self.activate_customer()
		self.add_principal_to_customer()

	# The principal rows' statuses are "Allow on Submit": a lead can move forward on a
	# submitted visit. Frappe skips validate() for these updates, so recompute here.
	def before_update_after_submit(self):
		self.set_principal_rows()

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
		filters = {"parenttype": "TP Customer", "parentfield": "principals", "parent": self.customer}
		for principal in dict.fromkeys(row.principal for row in self.principals):
			if frappe.db.exists("Customer Principal", {**filters, "principal": principal}):
				continue
			frappe.get_doc(
				{
					"doctype": "Customer Principal",
					**filters,
					"principal": principal,
					"idx": frappe.db.count("Customer Principal", filters) + 1,
				}
			).db_insert()
