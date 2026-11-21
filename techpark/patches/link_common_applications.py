# Last edited: 2026-11-13
# Copyright (c) 2026, Techpark International
"""Common Application list: every existing Technical Lead gets its Application from the master
(Customer Application), made per application name + the customer's industry when missing."""

import frappe


def execute():
	leads = frappe.get_all(
		"TP Technical Lead",
		filters={"application_master": ("is", "not set")},
		fields=["name", "customer", "application", "grinding_process", "product"],
	)
	industries = dict(frappe.get_all("TP Customer", fields=["name", "industry_domain"], as_list=True))
	for lead in leads:
		name = (lead.application or "").strip()
		if not name:
			continue
		industry = industries.get(lead.customer)
		master = frappe.db.get_value("Customer Application", {"application_name": name, "industry_domain": industry or ("is", "not set")})
		if not master:
			master = (
				frappe.get_doc(
					{
						"doctype": "Customer Application",
						"application_name": name,
						"industry_domain": industry,
						"product": lead.product,
						"grinding_process": lead.grinding_process,
						"is_active": 1,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		frappe.db.set_value("TP Technical Lead", lead.name, "application_master", master, update_modified=False)
		frappe.db.set_value("TP Customer Technical Lead", {"record": lead.name}, "application_master", master, update_modified=False)

	# Visits show the Application from their lead
	frappe.db.sql(
		"""
		update `tabDaily Visit Report` d
		join `tabTP Technical Lead` l on l.name = d.technical_lead
		set d.application_master = l.application_master
		where ifnull(d.application_master, '') = '' and ifnull(l.application_master, '') != ''
		"""
	)
