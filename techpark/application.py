# Last edited: 2026-11-14
# Copyright (c) 2026, Techpark International
"""Common Application list (Customer Application master), the same for every customer.

Applications are entered once in the master, with the defaults a visit fills (principal product
category, wheel spec, size). A customer's Technical Lead points to one of them and holds only
that customer's data (demand, share, machines, progress). A visit picks the application from the master;
the customer's Technical Lead for it is found, or made on save.
"""

import frappe
from frappe import _


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def application_query(doctype, txt, searchfield, start, page_len, filters):
	"""Application dropdown on a visit: one common list for every customer and
	every principal (the customer's own first)."""
	filters = filters or {}
	customer = filters.get("customer")
	own = tuple(
		frappe.get_all(
			"TP Technical Lead",
			filters={"customer": customer or "", "application_master": ("is", "set")},
			pluck="application_master",
		)
	) or ("",)
	return frappe.db.sql(
		f"""
		select a.name, a.application_name, p.product_name, a.grinding_process
		from `tabCustomer Application` a
		left join `tabCustomer Product` p on p.name = a.product
		where ifnull(a.is_active, 1) = 1
			and (a.application_name like %(txt)s or a.name like %(txt)s or p.product_name like %(txt)s)
		order by (a.name in %(own)s) desc, p.product_name, a.application_name
		limit %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "own": own, "start": start, "page_len": page_len},
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
			"Customer Application",
			application,
			["application_name", "grinding_process", "product", "supplier_product_category", "principal", "spec", "size", "production_line"],
			as_dict=True,
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
