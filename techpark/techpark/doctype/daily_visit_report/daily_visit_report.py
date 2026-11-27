# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
"""Daily Visit Report (DVR) — one record per customer visit, call or meeting.

Captures the visit once; demand records are created from it, and
the next action becomes a ToDo for the employee so the follow-up is tracked.

One application line per visit (since 2026-11-06): its fields are on the form and copied into a
single hidden DVR Principal row. Older visits may still hold several rows.
Principal-wise: every principal discussed is a row (DVR Principal) with two stages.
Development (introduction ... Successful Trial) comes first; the Sales stage (quotation ...
Order Won / Regularization) opens only once the trial was successful for that customer,
principal and product category, on this visit or an earlier submitted one. The old single
fields (principal, lead status / stage, stage completed) are kept as a summary of the rows.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate, today

from techpark.opportunity import refresh_opportunity, sync_visit
from techpark.permission import is_locked, is_manager
from techpark.masters import DEV_STATUS, K, SALES_STATUS, STAGE, key_of  # 2026-11-27: values found by App Key
from techpark.statuses import stage_progress, statuses_counting_as  # 2026-11-26: statuses are masters now

# 2026-11-26: Distributor Code is in TechPark Settings

# Status -> % of the whole cycle (Development up to 50%, Sales after). 2026-11-26: these are only the defaults
# (old patches use them): the live values are on the TP Development Status / TP Sales Status masters (statuses.py).
# The client's development cycle (CRM column list / Development Status format, 2026-11-06):
# enquiry -> sent to the principal -> offer -> trial PO -> sample -> trial -> bulk trial PO -> regularised.
DEVELOPMENT_PROGRESS = {
	"Introduction": 5,
	"Enquiry Received": 10,
	"Sent to Principal": 15,
	"Offer Received": 20,
	"Offer Submitted": 25,
	"Trial PO Received": 30,
	"Sample Received": 35,
	"Trial in Progress": 40,
	"Retest": 40,
	"Successful Trial": 50,
	"Trial Failed": 40,
	"Closed": 40,  # 2026-11-26
	"Bulk Trial Order": 55,  # 2026-11-27
	"Bulk Trial": 60,
	"Regularise": 70,
}
# Sales cycle after the trial (CRM column list): the bulk trial PO, then the enquiry / order / delivery /
# payment follow-ups of the regular business; each follow-up's Next Action is its reminder.
SALES_PROGRESS = {
	"Bulk Trial PO": 70,
	"Enquiry Follow-up": 75,
	"Order Follow-up": 80,
	"Delivery Follow-up": 85,
	"Payment Follow-up": 90,
	"On Hold": 50,
	"Lost": 50,  # 2026-11-27: was Cancelled
}
STAGE_PROGRESS = {**DEVELOPMENT_PROGRESS, **SALES_PROGRESS}
TRIAL_DONE = "Successful Trial"
TRIAL_STATUSES = ("Trial PO Received", "Sample Received", "Trial in Progress", "Retest")
SALES_FOLLOW_UPS = ("Enquiry Follow-up", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up")
# An order is in: the customer is buying (an enquiry follow-up is not an order yet).
WON_STATUSES = ("Bulk Trial PO", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up")  # 2026-11-27: Regularization -> Regularise (Open)
LOST_STATUSES = ("Lost", "Trial Failed")  # 2026-11-27: Cancelled renamed Lost
GENERAL_APPLICATION = "General"
LEAD_STATUS = "TP Lead Status"
# 2026-11-27 (phase 2): the status / stage names in this file are App Keys; the values can be renamed, so the code
# compares and sets through these (current names)


def trial_done():
	return K(DEV_STATUS, TRIAL_DONE)


def stage_key(name):
	"""Development / Sales (the App Key) of a stage's current name."""
	return key_of(STAGE, name)


def is_sales(stage):
	return stage_key(stage) == "Sales"


def is_development(stage):
	return stage_key(stage) == "Development"
# One application line per visit: these fields on the visit are copied into its (hidden) principal row,
# which opportunities, follow-ups and reports read.
LINE_FIELDS = (
	"principal", "technical_lead", "application", "supplier_product_category", "spec", "size",
	"development_status", "sales_status",
)
LINE_RESULT_FIELDS = (*LINE_FIELDS, "development_done_before", "opportunity")

# Old single Lead Stage / Status (and the stages used before 2026-11-06) -> (stage, development
# status, sales status) of a principal row.
OLD_STAGES = {
	"Introduction": ("Development", "Introduction", None),
	"Received Enquiry": ("Development", "Enquiry Received", None),
	"Requirement Shared": ("Development", "Enquiry Received", None),
	"Technical Discussion": ("Development", "Enquiry Received", None),
	"Sample / Trial Planned": ("Development", "Trial PO Received", None),
	"Trial / Sample": ("Development", "Trial in Progress", None),
	"Quotation Submitted": ("Development", "Offer Submitted", None),
	"Negotiation": ("Development", "Offer Submitted", None),
	"Order Received": ("Sales", TRIAL_DONE, "Bulk Trial PO"),
	"Order Won": ("Sales", TRIAL_DONE, "Bulk Trial PO"),
	"Order Lost": ("Sales", TRIAL_DONE, "Lost"),  # 2026-11-27
}


def row_from_lead(lead_stage, lead_status):
	"""Development / Sales status of a principal row for an old-style Lead Stage + Lead Status
	(visits entered on the customer's Visits tab, and visits made before principal rows existed).
	2026-11-27: worked out on App Keys, returned as the current names."""
	dev_key, sales_key = key_of(DEV_STATUS, lead_stage), key_of(SALES_STATUS, lead_stage)
	lead_status = key_of(LEAD_STATUS, lead_status)
	if dev_key in DEVELOPMENT_PROGRESS:
		stage, development, sales = "Development", dev_key, None
	elif sales_key in SALES_PROGRESS:
		stage, development, sales = "Sales", TRIAL_DONE, sales_key
	else:
		stage, development, sales = OLD_STAGES.get(lead_stage, ("Development", "Introduction", None))
	if lead_status == "Won":
		stage, development, sales = "Sales", TRIAL_DONE, sales if sales in WON_STATUSES else "Bulk Trial PO"
	elif lead_status == "Lost":
		if stage == "Sales":
			sales = "Lost"  # 2026-11-27
		else:
			development = "Trial Failed"
	elif lead_status == "On Hold" and stage == "Sales":
		sales = "On Hold"
	return {"stage": K(STAGE, stage), "development_status": K(DEV_STATUS, development), "sales_status": K(SALES_STATUS, sales)}


def dvr_stage(stages):
	"""Stage of the whole visit from its principal rows' stages."""
	stages = {stage_key(s) for s in stages}  # 2026-11-27: by App Key
	if stages == {"Development", "Sales"}:
		return K(STAGE, "Development + Sales")
	return K(STAGE, "Sales" if "Sales" in stages else "Development")


@frappe.whitelist()
def development_done(customer=None, principal=None, supplier_product_category=None, exclude=None, application=None, spec=None):
	"""True when an earlier submitted visit of this customer recorded a successful trial (or already
	reached the Sales stage) for this application line, principal, product category and spec."""
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
				and ifnull(r.application, '') = %(application)s and ifnull(r.spec, '') = %(spec)s
				and (r.development_status = %(done)s or r.stage = %(sales)s)
			limit 1
			""",
			{
				"customer": customer,
				"principal": principal,
				"category": supplier_product_category or "",
				"application": (application or "").strip() or GENERAL_APPLICATION,
				"spec": (spec or "").strip(),
				"exclude": exclude or "",
				"done": trial_done(),  # 2026-11-27: current names
				"sales": K(STAGE, "Sales"),
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
		self.row_to_line()  # visits made before the line moved onto the form

	def validate(self):
		from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

		self.distributor = get_setting("distributor_code")
		self.validate_visited_by()
		self.clean_joint_visitors()
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

	def clean_joint_visitors(self):
		"""Colleagues on the visit: not the Employee, each once."""
		seen = {self.visited_by}
		rows = []
		for row in self.get("joint_visitors") or []:
			if row.user and row.user not in seen:
				seen.add(row.user)
				rows.append(row)
		self.set("joint_visitors", rows)

	def validate_dates(self):
		if getdate(self.visit_date) > getdate(today()):
			frappe.throw(_("Visit Date cannot be in the future."))
		if self.next_action_date and getdate(self.next_action_date) < getdate(self.visit_date):
			frappe.throw(_("Next Action By cannot be before the Visit Date."))

	def validate_plant(self):
		"""One customer = one site: the (hidden) plant is the customer's, set in before_validate."""
		if not self.plant:
			self.plant_name = None
			return
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

	def set_line_from_lead(self):
		"""2026-11-26: the visit's line is the customer's Technical Lead (made on the customer's Technical Leads tab
		first, client): its principal, application, product and production line are copied. No lead is made here."""
		if not self.technical_lead:
			return
		lead = frappe.db.get_value(
			"TP Technical Lead", self.technical_lead,
			["customer", "principal", "application_master", "product", "production_line",
			 "application", "supplier_product_category", "spec", "size", "size_od", "size_t", "size_id"], as_dict=True,
		)
		if not lead:
			return
		if lead.customer != self.customer:
			frappe.throw(_("Technical Lead {0} belongs to another customer.").format(frappe.bold(self.technical_lead)))
		self.principal = lead.principal
		self.application_master = lead.application_master
		self.customer_product = lead.product
		self.production_line = lead.production_line
		# 2026-11-27: all autofilled fields are the lead's (read only on the visit; changed on the Technical Lead only)
		self.application = lead.application or self.application
		self.supplier_product_category = lead.supplier_product_category
		self.spec = lead.spec
		self.size = lead.size or " x ".join(v for v in (lead.size_od, lead.size_t, lead.size_id) if v)

	def set_lead_from_application(self):
		"""Before 2026-11-26: application picked from the common list made the customer's Technical Lead. Not used now."""
		if not (self.get("application_master") and self.customer and self.principal):
			return
		# 2026-11-26: the lead must also be of the visit's Production Line (an application can run on several lines)
		if self.technical_lead:
			lead = frappe.db.get_value("TP Technical Lead", self.technical_lead, ["application_master", "production_line", "product"], as_dict=True)
			if (
				lead
				and lead.application_master == self.application_master
				and (not self.production_line or cstr(lead.production_line).strip().lower() == cstr(self.production_line).strip().lower())
				and (not self.customer_product or cstr(lead.product) == cstr(self.customer_product))  # 2026-11-26: Product too
			):
				return
		from techpark.application import get_or_create_lead

		self.technical_lead = get_or_create_lead(
			self.customer, self.principal, self.application_master,
			product=self.customer_product, production_line=self.production_line,
			supplier_product_category=self.supplier_product_category,
		)  # 2026-11-21: the visit's line details go to the new lead

	def line_to_row(self):
		"""The visit's Application Line fields -> its first principal row (made if missing)."""
		# 2026-11-27: also on Submit (docstatus is already 1 then); not on later changes to a submitted visit
		if self._action != "update_after_submit":
			self.set_line_from_lead()  # 2026-11-26: was set_lead_from_application (made the lead from the visit)
		if not (self.development_status or self.sales_status or self.technical_lead):
			return  # no line entered here (e.g. a visit from the customer's Visits tab): add_row_from_summary
		row = self.principals[0] if self.principals else self.append("principals", {})
		for field in LINE_FIELDS:
			row.set(field, self.get(field))

	def row_to_line(self):
		"""The first principal row's (validated) values -> the visit's Application Line fields."""
		if not self.get("principals"):
			return
		row = self.principals[0]
		for field in LINE_RESULT_FIELDS:
			self.set(field, row.get(field))

	def set_principal_rows(self):
		"""Stage and progress of every principal row, then the summary fields."""
		self.line_to_row()
		self.add_row_from_summary()
		if not self.principals:
			frappe.throw(_("Add at least one Principal discussed on this visit."))
		seen = set()
		for row in self.principals:
			self.validate_category(row)
			self.set_application(row)
			key = (row.application, row.principal, str(row.supplier_product_category or ""), row.spec or "")
			if key in seen:
				frappe.throw(
					_("{0} is entered twice.").format(
						" / ".join(p for p in (row.application, row.principal, row.category_name, row.spec) if p)
					)
				)
			seen.add(key)
			self.set_row_stage(row)
		self.set_summary()
		self.row_to_line()

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
		if is_sales(row.stage) and not development_done(
			self.customer, row.principal, row.supplier_product_category, self.name
		):
			frappe.throw(
				_("{0}: {1} needs a Successful Trial first. Record the trial for this principal before the sale.").format(
					frappe.bold(row.principal), frappe.bold(row.sales_status)
				)
			)

	def line_label(self, row):
		"""How messages name a line: the application on a one-line visit, the row on older multi-line ones."""
		name = frappe.bold(" · ".join(p for p in (row.application, row.principal) if p) or _("Application line"))
		return name if len(self.principals) <= 1 else _("Row {0} ({1})").format(row.idx, name)

	def set_application(self, row):
		"""Every row is one application line (its development is followed as a TP Opportunity).
		Empty: the visit's Segment / Line, else "General"."""
		if row.get("technical_lead"):
			# The row's application is its Technical Lead's, which must be this customer's
			lead = frappe.db.get_value("TP Technical Lead", row.technical_lead, ["customer", "application"], as_dict=True)
			if lead and lead.customer != self.customer:
				frappe.throw(
					_("Application {0} is a Technical Lead of another customer.").format(frappe.bold(lead.application))
				)
			# A submitted visit keeps the name it was made with (the lead may be renamed later)
			if self.docstatus == 0 or not row.application:
				row.application = (lead and lead.application) or row.application
		for field in ("application", "spec", "size"):
			row.set(field, (row.get(field) or "").strip() or None)
		if not row.application:
			row.application = (
				frappe.db.get_value("Customer Segment Application", self.segment_application, "sub_category_line")
				if self.segment_application
				else None
			) or GENERAL_APPLICATION

	def validate_category(self, row):
		# Product categories are numbered (autoincrement): the name is what people read.
		row.category_name = (
			frappe.db.get_value("Supplier Product Category", row.supplier_product_category, "category_name")
			if row.supplier_product_category
			else None
		)
		if not row.supplier_product_category:
			return
		category_principal = frappe.db.get_value("Supplier Product Category", row.supplier_product_category, "principal")
		if category_principal != row.principal:
			frappe.throw(
				_("{0}: Product Category {1} belongs to {2}, not {3}.").format(
					self.line_label(row),
					frappe.bold(row.category_name or row.supplier_product_category),
					frappe.bold(category_principal),
					frappe.bold(row.principal),
				)
			)

	def set_row_stage(self, row):
		row.development_done_before = 1 if development_done(
			self.customer, row.principal, row.supplier_product_category, self.name, row.application, row.spec
		) else 0
		# 2026-11-27: stages / statuses by App Key (they can be renamed)
		visit_stage = self.dvr_stage if stage_key(self.dvr_stage) in ("Development", "Sales") else None
		# Strict rules for new entries; already-submitted visits keep their recorded rows.
		strict = self._action != "update_after_submit"
		# 2026-11-26: a successful trial stays in Development until the lead's Progress is Regularised (client);
		# only a regularised lead (lead Stage = Sales) takes Sales visits, and then no Development visits.
		lead_stage = frappe.db.get_value("TP Technical Lead", row.technical_lead, "stage") if row.get("technical_lead") else None
		if is_sales(visit_stage):
			# A Sales visit follows lines whose development is complete
			row.development_status = trial_done()
			if strict and row.get("technical_lead") and not is_sales(lead_stage):
				frappe.throw(
					_("{0} is not Regularised yet: set its Technical Lead's Progress to Regularised to move it to Sales.").format(
						self.line_label(row)
					)
				)
		elif is_development(visit_stage):
			if strict and is_sales(lead_stage):
				frappe.throw(
					_("{0} is Regularised (Sales stage). Set the visit's Stage to Sales.").format(self.line_label(row))
				)
		elif row.development_done_before:
			row.development_status = trial_done()  # older visits without a Stage
		if is_sales(visit_stage) and strict and not row.sales_status:
			frappe.throw(
				_("{0}: select the Sales Status.").format(self.line_label(row))
			)
		if not row.development_status:
			frappe.throw(
				_("{0}: select the Development Status.").format(self.line_label(row))
			)
		# 2026-11-26: the visit's Stage (older visits without one: Sales from the successful trial on)
		row.stage = visit_stage or K(STAGE, "Sales" if row.development_status == trial_done() else "Development")
		if row.sales_status and not is_sales(row.stage):
			frappe.throw(
				_("{0}: Sales Status {1} can be set only after a Successful Trial.").format(
					self.line_label(row), frappe.bold(row.sales_status)
				)
			)
		row.progress = stage_progress().get(row.sales_status or row.development_status, 0)  # 2026-11-26: % from the status master
		if row.next_action_date and getdate(row.next_action_date) < getdate(self.visit_date):
			frappe.throw(
				_("{0}: Next Action By cannot be before the Visit Date.").format(self.line_label(row))
			)

	def set_summary(self):
		"""The single fields other screens read: first principal, the furthest status, overall lead status."""
		rows = self.principals
		self.principal = rows[0].principal
		self.supplier_product_category = rows[0].supplier_product_category
		self.principal_list = ", ".join(dict.fromkeys(row.principal for row in rows))
		# "Ch-6 O/R Grove · Noritake: Trial in Progress" per line, for the customer's Visits tab
		self.principal_summary = "\n".join(
			"{0}: {1}".format(
				" · ".join(p for p in (row.application, row.principal, row.category_name) if p),
				row.sales_status or row.development_status,
			)
			for row in rows
		)
		if stage_key(self.dvr_stage) not in ("Development", "Sales"):
			# Not chosen (visits added from the customer's Visits tab) or an older mixed visit
			self.dvr_stage = dvr_stage(row.stage for row in rows)
		furthest = max(rows, key=lambda row: row.progress or 0)
		self.lead_stage = furthest.sales_status or furthest.development_status
		self.stage_completed = furthest.progress or 0
		statuses = [row.sales_status or row.development_status for row in rows]
		# 2026-11-26: what a status counts as (Won / Lost / On Hold) is set on its master
		if any(s in statuses_counting_as("Won") for s in statuses):
			self.lead_status = "Won"
		elif all(s in statuses_counting_as("Lost") for s in statuses):
			self.lead_status = "Lost"
		elif all(s in statuses_counting_as("On Hold") for s in statuses):
			self.lead_status = "On Hold"
		else:
			self.lead_status = "Prospect"

	def on_submit(self):
		self.create_follow_up()
		self.activate_customer()
		self.add_principal_to_customer()
		self.set_lead_progress()  # 2026-11-27: before the line is refreshed (Regularised moves it, Lost closes it)
		sync_visit(self)
		self.set_line_opportunity()
		self.update_lead_spec_size()

	def set_lead_progress(self):
		"""2026-11-27 (client): the visit's status sets its Technical Lead's Progress (status master > Sets Lead
		Progress): Introduction ... -> Under Development, Trial Failed -> Evaluation Failed (lead closed),
		Regularise -> Regularised (lead to Sales), Lost -> Lost (lead closed). Empty: Progress unchanged."""
		from techpark.statuses import progress_effect, status_lead_progress

		for row in self.principals:
			if not row.get("technical_lead"):
				continue
			stage = "Sales" if is_sales(row.stage) else "Development"  # App Key
			progress = status_lead_progress(stage, row.sales_status if stage == "Sales" else row.development_status)
			lead = frappe.db.get_value("TP Technical Lead", row.technical_lead, ["progress", "last_visit"], as_dict=True) or {}
			if not progress or lead.get("progress") == progress:
				continue
			if lead.get("last_visit") and getdate(self.visit_date) < getdate(lead["last_visit"]):
				continue  # an older visit edited after submit: the lead follows its latest visit
			effect = progress_effect(progress)
			values = {"progress": progress, "is_closed": 1 if effect.closes_lead else 0}
			if effect.moves_to_stage:
				values["stage"] = effect.moves_to_stage
			frappe.db.set_value("TP Technical Lead", row.technical_lead, values, update_modified=False)
			# the customer tab row has no Closed column (2026-11-27 fix: "Unknown column 'is_closed'")
			row_values = {k: v for k, v in values.items() if k != "is_closed"}
			frappe.db.set_value("TP Customer Technical Lead", {"record": row.technical_lead}, row_values, update_modified=False)
			frappe.get_doc("TP Technical Lead", row.technical_lead).add_comment(
				"Info", _("Progress {0} (visit {1}: {2})").format(frappe.bold(progress), self.name, row.sales_status or row.development_status)
			)
			if effect.moves_to_stage and effect.moves_to_stage != row.stage:
				self.show_stage_moved(row, progress, effect.moves_to_stage)
			elif effect.closes_lead:
				self.show_lead_closed(row, progress)  # 2026-11-27: Trial Failed / Lost

	def lead_line(self, row):
		"""The lead as a link + its application · principal, for the pop-ups."""
		from frappe.utils import escape_html, get_url_to_form

		line = " · ".join(escape_html(p) for p in (row.application, row.principal) if p)
		lead = f'<a href="{get_url_to_form("TP Technical Lead", row.technical_lead)}">{escape_html(row.technical_lead)}</a>'
		return lead, line

	def show_lead_closed(self, row, progress):
		"""2026-11-27 (client): a pop-up after submit when the visit closes its lead (Trial Failed / Lost)."""
		from frappe.utils import escape_html

		lead, line = self.lead_line(row)
		status = row.sales_status or row.development_status
		frappe.msgprint(
			_(
				"Technical Lead {0} ({1}) is now {2}{3}, so the lead has been closed."
				"<br><br>It will no longer be offered on new visits or shown on the boards. To reopen it, change its "
				"Progress on the Technical Lead."
			).format(lead, line, frappe.bold(progress), f" ({escape_html(status)})" if status != progress else ""),
			title=_("Lead closed: {0}").format(progress),
			indicator="red",
		)

	def show_stage_moved(self, row, progress, new_stage):
		"""2026-11-27 (client): a pop-up after submit when the lead moves on (Regularise -> Sales)."""
		lead, line = self.lead_line(row)
		frappe.msgprint(
			_(
				"Congratulations! Technical Lead {0} ({1}) is now {2} and has moved from the {3} stage to the {4} stage."
				"<br><br>Its next visits will be {4} visits, and you will find it on the {4} Board."
			).format(lead, line, frappe.bold(progress), frappe.bold(row.stage), frappe.bold(new_stage)),
			title=_("Lead moved to {0}").format(new_stage),
			indicator="green",
		)

	def update_lead_spec_size(self):
		"""2026-11-21: the visit's Principal Product Spec / Size go to its Technical Lead (client).
		2026-11-25: and its Principal Product Category.
		2026-11-27: not any more: a visit cannot change its Technical Lead's data (read only once picked; the lead
		is changed on its own form, which updates its visits)."""

	def set_line_opportunity(self):
		"""sync_visit links the row to its TP Opportunity; show it on the visit too."""
		if self.principals and self.principals[0].opportunity != self.get("opportunity"):
			self.db_set("opportunity", self.principals[0].opportunity, update_modified=False)

	# The principal rows' statuses are "Allow on Submit": a lead can move forward on a
	# submitted visit. Frappe skips validate() for these updates, so recompute here.
	def before_update_after_submit(self):
		self.set_principal_rows()

	def on_update_after_submit(self):
		self.activate_customer()
		self.set_lead_progress()  # 2026-11-27
		sync_visit(self)
		self.set_line_opportunity()
		self.update_lead_spec_size()  # 2026-11-21

	def on_cancel(self):
		for todo in [self.follow_up, *(row.follow_up for row in self.principals)]:
			if todo and frappe.db.get_value("ToDo", todo, "status") == "Open":
				frappe.db.set_value("ToDo", todo, "status", "Cancelled")
		# The opportunities fall back to their latest remaining visit.
		for name in dict.fromkeys(row.opportunity for row in self.principals if row.opportunity):
			refresh_opportunity(name)

	def create_follow_up(self):
		"""A ToDo for the visit's Next Action, and one per principal row with its own Next Action."""
		if self.next_action:
			self.db_set("follow_up", self.make_todo(self.next_action, self.next_action_date))
		for row in self.principals:
			if row.next_action and not row.follow_up:
				action = _("{0}: {1}").format(row.principal, row.next_action)
				row.db_set("follow_up", self.make_todo(action, row.next_action_date))

	def make_todo(self, action, date):
		return (
			frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": self.visited_by,
					"date": date,
					"description": _("{0} — {1}").format(self.customer_name, action),
					"reference_type": self.doctype,
					"reference_name": self.name,
					"assigned_by": frappe.session.user,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def activate_customer(self):
		"""A won visit turns a Prospect into an Active Customer."""
		if self.lead_status != "Won":
			return
		from techpark.masters import CUSTOMER_STATUS

		# 2026-11-27: Customer Status values by App Key (they can be renamed)
		if frappe.db.get_value("TP Customer", self.customer, "customer_status") == K(CUSTOMER_STATUS, "Prospect"):
			active = K(CUSTOMER_STATUS, "Active Customer")
			frappe.db.set_value("TP Customer", self.customer, "customer_status", active)
			frappe.get_doc("TP Customer", self.customer).add_comment(
				"Info", _("Marked {0} from won visit {1}").format(active, self.name)
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
