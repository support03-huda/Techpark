# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""Common Application list (Customer Application master), the same for every customer.

Applications are entered once in the master, with the defaults a visit fills (principal product
category, wheel spec, size). A customer's Technical Lead points to one of them and holds only
that customer's data (demand, share, machines, progress). A visit picks the application from the master;
the customer's Technical Lead for it is found, or made on save.
"""

import frappe
from frappe import _
from frappe.utils import cstr


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


def find_lead(customer, principal, application, production_line=None, product=None):
	"""2026-11-26: the customer's lead for this application, Product and Production Line: any of them
	different = another lead (client). Category / Spec / Size only update a lead.
	No product given = any product; no line and no product given and only one lead: that one."""
	leads = frappe.db.sql(
		"""select l.name, ifnull(l.production_line, '') as production_line, ifnull(l.product, '') as product,
			ifnull(p.product_name, '') as product_name
		from `tabTP Technical Lead` l left join `tabCustomer Product` p on p.name = l.product
		where l.customer = %s and l.principal = %s and l.application_master = %s order by l.creation""",
		(customer, principal, application),
		as_dict=True,
	)
	line, product = cstr(production_line).strip().lower(), cstr(product)
	match = [
		l.name for l in leads
		if l.production_line.strip().lower() == line and (not product or cstr(l.product) == product)
	]
	if match:
		return match[0], leads
	if not line and not product and len(leads) == 1:
		return leads[0].name, leads
	return None, leads


@frappe.whitelist()
def line_details(customer, principal, application, production_line=None):
	"""What a visit fills when an application is picked: the customer's Technical Lead for it (if any).
	2026-11-26: with several production lines, all of them come back and the visit asks which one."""
	lead, leads = find_lead(customer, principal, application, production_line)
	return {
		"lead": lead,
		"leads": leads,
		"application": frappe.db.get_value(
			"Customer Application",
			application,
			["application_name", "grinding_process", "product", "supplier_product_category", "principal", "spec", "size", "production_line"],
			as_dict=True,
		),
	}


def get_or_create_lead(customer, principal, application, **defaults):
	"""The customer's Technical Lead for this application and production line (made on the first visit)."""
	# 2026-11-21: a new lead takes the visit's Product / Production Line / Category (no longer on the master)
	# 2026-11-26: found by its Production Line too; several lines and none picked -> ask
	lead, leads = find_lead(customer, principal, application, defaults.get("production_line"), defaults.get("product"))
	if lead:
		return lead
	if leads and not cstr(defaults.get("production_line")).strip():
		frappe.throw(
			_("This customer has this application on {0} production lines ({1}): enter the Production Line of this visit.").format(
				len(leads), ", ".join(l.production_line or _("no line") for l in leads)
			)
		)
	# 2026-11-26: Technical Leads are made only from a DVR (client); the flag lets this insert through
	frappe.flags.tp_lead_from_dvr = True
	try:
		return (
			frappe.get_doc(
				{
					"doctype": "TP Technical Lead", "customer": customer, "principal": principal, "application_master": application,
					**{k: v for k, v in defaults.items() if v},
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	finally:
		frappe.flags.tp_lead_from_dvr = False
