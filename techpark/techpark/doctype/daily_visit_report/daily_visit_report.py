# Copyright (c) 2026, Techpark International
"""Daily Visit Report (DVR) — one record per customer visit.

Captures the visit once; demand and expense records are created from it, and
the next action becomes a ToDo for the employee so the follow-up is tracked.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

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


class DailyVisitReport(Document):
	def validate(self):
		self.validate_dates()
		self.validate_plant()
		self.set_stage_completed()

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

	def set_stage_completed(self):
		if self.lead_status == "Won":
			self.lead_stage = "Order Received"
		self.stage_completed = STAGE_PROGRESS.get(self.lead_stage, 0)

	def on_submit(self):
		self.create_follow_up()
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
