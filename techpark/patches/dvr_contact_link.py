"""DVR Contact Person became a link to Customer Contact: fill it on existing visits from
the contact name they carry, with the contact's designation and phone."""

import frappe

from techpark.techpark.doctype.daily_visit_report.daily_visit_report import find_contact


def execute():
	for dvr in frappe.get_all(
		"Daily Visit Report",
		filters={"contact": ("is", "not set"), "contact_person": ("is", "set")},
		fields=["name", "customer", "contact_person"],
	):
		contact = find_contact(dvr.customer, dvr.contact_person)
		if not contact:
			continue
		designation, phone = frappe.db.get_value("Customer Contact", contact, ["designation", "phone"])
		frappe.db.set_value(
			"Daily Visit Report",
			dvr.name,
			{"contact": contact, "contact_designation": designation, "contact_phone": phone},
			update_modified=False,
		)
