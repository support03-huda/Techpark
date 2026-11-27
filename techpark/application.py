# Last edited: 2026-11-27
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


# 2026-11-26: the visit picks one of the customer's Technical Leads (made on the customer first, client)
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def lead_query(doctype, txt, searchfield, start, page_len, filters):
	"""Technical Lead dropdown on a visit: the customer's leads.
	2026-11-26: shown as Principal, Product, Application, Production Line, Category, Size (client order).
	2026-11-27: Spec added between Category and Size."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)  # 2026-11-27: also when called with JSON filters
	customer = (filters or {}).get("customer") or ""
	principal = (filters or {}).get("principal") or ""  # 2026-11-26: only the picked principal's leads
	stage = (filters or {}).get("stage") or ""  # 2026-11-26: Development visit -> development leads, Sales -> regularised ones
	return frappe.db.sql(
		"""
		select l.name, l.principal, p.product_name, l.application, l.production_line, c.category_name, l.spec, l.size, l.current_status
		from `tabTP Technical Lead` l
		left join `tabCustomer Product` p on p.name = l.product
		left join `tabSupplier Product Category` c on c.name = l.supplier_product_category
		where l.customer = %(customer)s and (%(principal)s = '' or l.principal = %(principal)s)
			and ifnull(l.is_closed, 0) = 0
			and (%(stage)s = '' or ifnull(l.stage, '') in ('', %(stage)s))
			and (l.name like %(txt)s or l.application like %(txt)s or ifnull(p.product_name, '') like %(txt)s
				or ifnull(l.production_line, '') like %(txt)s or l.principal like %(txt)s)
		order by l.last_visit desc, l.creation desc
		limit %(start)s, %(page_len)s
		""",
		{"customer": customer, "principal": principal, "stage": stage, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


# 2026-11-26: Technical Lead field -> the same data on its visits (DVR form fields)
LEAD_TO_VISIT = {
	"principal": "principal",
	"product": "customer_product",
	"application_master": "application_master",
	"production_line": "production_line",
	"supplier_product_category": "supplier_product_category",
	"size": "size",
	"spec": "spec",
}


def lead_visits(lead):
	"""2026-11-26: the visits (DVR, not cancelled) of a Technical Lead: on the form or on its line row."""
	return frappe.db.sql_list(
		"""select distinct d.name from `tabDaily Visit Report` d
		left join `tabDVR Principal` r on r.parent = d.name and r.parenttype = 'Daily Visit Report'
		where d.docstatus < 2 and (d.technical_lead = %(lead)s or r.technical_lead = %(lead)s)""",
		{"lead": lead},
	)


@frappe.whitelist()
def lead_visit_list(leads):
	"""2026-11-26: {lead: [{name, visit_date, dvr_stage, docstatus}]} for the "this will affect N visits" dialog."""
	leads = frappe.parse_json(leads) if isinstance(leads, str) else leads
	out = {}
	for lead in leads or []:
		if not frappe.has_permission("TP Technical Lead", "read", lead):
			continue
		names = lead_visits(lead)
		out[lead] = frappe.get_all(
			"Daily Visit Report", filters={"name": ("in", names or [""])},
			fields=["name", "visit_date", "dvr_stage", "docstatus"], order_by="visit_date desc",
		) if names else []
	return out


@frappe.whitelist()
def lead_visit_counts(leads):
	"""2026-11-26: {lead: number of visits} for the "this will affect N visits" question."""
	leads = frappe.parse_json(leads) if isinstance(leads, str) else leads
	return {lead: len(lead_visits(lead)) for lead in leads or [] if frappe.has_permission("TP Technical Lead", "read", lead)}


def update_lead_visits(lead_doc, changed):
	"""2026-11-26: the lead was changed (user confirmed): its visits, their line rows and opportunity take the new data."""
	visits = lead_visits(lead_doc.name)
	if not visits:
		return 0
	form = {LEAD_TO_VISIT[f]: lead_doc.get(f) for f in changed if f in LEAD_TO_VISIT}
	if "application_master" in changed:
		form["application"] = lead_doc.application
		form["grinding_process"] = lead_doc.grinding_process
	if "product" in changed:
		form["product_name"] = frappe.db.get_value("Customer Product", lead_doc.product, "product_name") if lead_doc.product else None
	row = {f: v for f, v in form.items() if f in ("principal", "application", "supplier_product_category", "spec", "size")}
	if "supplier_product_category" in changed:
		row["category_name"] = (
			frappe.db.get_value("Supplier Product Category", lead_doc.supplier_product_category, "category_name")
			if lead_doc.supplier_product_category else None
		)
	for name in visits:
		if form:
			frappe.db.set_value("Daily Visit Report", name, form, update_modified=False)
		if row:
			frappe.db.sql(
				f"""update `tabDVR Principal` set {", ".join(f"`{f}` = %({f})s" for f in row)}
				where parent = %(parent)s and parenttype = 'Daily Visit Report'
					and (technical_lead = %(lead)s or idx = 1)""",
				{**row, "parent": name, "lead": lead_doc.name},
			)
	# the development / sales line of the lead
	from techpark.opportunity import refresh_opportunity

	opps = set(frappe.db.sql_list(
		"""select distinct opportunity from `tabDVR Principal`
		where parenttype = 'Daily Visit Report' and parent in %(v)s and ifnull(opportunity, '') != ''""",
		{"v": visits},
	))
	if lead_doc.opportunity:
		opps.add(lead_doc.opportunity)
	for opp in opps:
		keys = {k: v for k, v in (("principal", lead_doc.principal), ("application", lead_doc.application)) if v and k in row}
		if keys:
			frappe.db.set_value("TP Opportunity", opp, keys, update_modified=False)
		refresh_opportunity(opp)
	return len(visits)


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
