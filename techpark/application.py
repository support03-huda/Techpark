# Copyright (c) 2026, Techpark International
"""Common Application list (Customer Application master), industry / product-wise.

Applications are the same for every customer of an industry (e.g. Bearings -> Ball Bearing -> BB OR Groove),
so they are entered once in the master. A customer's Technical Lead points to one of them and holds only
that customer's data (demand, share, machines, progress). A visit picks the application from the master;
the customer's Technical Lead for it is found, or made on save.
"""

import frappe
from frappe import _


def customer_industry(customer):
	return frappe.db.get_value("TP Customer", customer, "industry_domain") if customer else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def application_query(doctype, txt, searchfield, start, page_len, filters):
	"""Application dropdown on a visit: the customer's own applications first, then the common
	applications of the customer's industry (and those without an industry)."""
	filters = filters or {}
	customer = filters.get("customer")
	industry = customer_industry(customer)
	own = tuple(
		frappe.get_all(
			"TP Technical Lead",
			filters={"customer": customer or "", "application_master": ("is", "set")},
			pluck="application_master",
		)
	) or ("",)
	industry_condition = "or ifnull(a.industry_domain, '') in ('', %(industry)s)" if industry else "or 1 = 1"
	return frappe.db.sql(
		f"""
		select a.name, a.application_name, a.industry_domain, a.grinding_process
		from `tabCustomer Application` a
		where ifnull(a.is_active, 1) = 1
			and (a.application_name like %(txt)s or a.name like %(txt)s)
			and (a.name in %(own)s {industry_condition})
		order by (a.name in %(own)s) desc, a.application_name
		limit %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "own": own, "industry": industry, "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def line_details(customer, principal, application):
	"""What a visit fills when an application is picked: the customer's Technical Lead for it (if any)."""
	lead = frappe.db.get_value(
		"TP Technical Lead",
		{"customer": customer, "principal": principal, "application_master": application},
		"name",
	)
	return {
		"lead": lead,
		"application": frappe.db.get_value(
			"Customer Application", application, ["application_name", "grinding_process", "product"], as_dict=True
		),
	}


def get_or_create_lead(customer, principal, application):
	"""The customer's Technical Lead for this application (made on the first visit)."""
	lead = frappe.db.get_value(
		"TP Technical Lead", {"customer": customer, "principal": principal, "application_master": application}, "name"
	)
	if lead:
		return lead
	return (
		frappe.get_doc(
			{"doctype": "TP Technical Lead", "customer": customer, "principal": principal, "application_master": application}
		)
		.insert(ignore_permissions=True)
		.name
	)
