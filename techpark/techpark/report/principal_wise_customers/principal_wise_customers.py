# Copyright (c) 2026, Techpark International
"""Customer list principal-wise: every customer under each Principal it works with,
with its submitted visits for that principal."""

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Max


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "principal", "label": _("Principal"), "fieldtype": "Link", "options": "Principal", "width": 120},
		{"fieldname": "customer", "label": _("Customer Code"), "fieldtype": "Link", "options": "TP Customer", "width": 110},
		{"fieldname": "customer_name", "label": _("Customer"), "fieldtype": "Data", "width": 220},
		{"fieldname": "customer_status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "territory_region", "label": _("Region"), "fieldtype": "Link", "options": "Territory Region", "width": 110},
		{"fieldname": "zone", "label": _("Zone"), "fieldtype": "Data", "width": 80},
		{"fieldname": "industry_domain", "label": _("Industry"), "fieldtype": "Data", "width": 140},
		{"fieldname": "handled_by", "label": _("Handled By"), "fieldtype": "Data", "width": 180},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 70},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Date", "width": 100},
	]


def get_data(filters):
	customer = frappe.qb.DocType("TP Customer")
	link = frappe.qb.DocType("Customer Principal")
	query = (
		frappe.qb.from_(link)
		.join(customer)
		.on(link.parent == customer.name)
		.select(
			link.principal,
			customer.name.as_("customer"),
			customer.customer_name,
			customer.customer_status,
			customer.territory_region,
			customer.zone,
			customer.industry_domain,
		)
		.where((link.parenttype == "TP Customer") & (link.parentfield == "principals"))
		.orderby(link.principal)
		.orderby(customer.customer_name)
	)
	if filters.principal:
		query = query.where(link.principal == filters.principal)
	for field in ("customer_status", "territory_region", "zone"):
		if filters.get(field):
			query = query.where(customer[field] == filters[field])
	rows = query.run(as_dict=True)
	if not rows:
		return []

	customers = list({r.customer for r in rows})
	visits = _visit_stats(customers)
	agents = _agents(customers)
	for r in rows:
		stats = visits.get((r.customer, r.principal), {})
		r.visits = stats.get("visits", 0)
		r.last_visit = stats.get("last_visit")
		r.handled_by = ", ".join(agents.get(r.customer, []))
	return rows


def _visit_stats(customers):
	dvr = frappe.qb.DocType("Daily Visit Report")
	result = (
		frappe.qb.from_(dvr)
		.select(dvr.customer, dvr.principal, Count(dvr.name).as_("visits"), Max(dvr.visit_date).as_("last_visit"))
		.where((dvr.docstatus == 1) & dvr.customer.isin(customers) & dvr.principal.isnotnull())
		.groupby(dvr.customer, dvr.principal)
	).run(as_dict=True)
	return {(r.customer, r.principal): r for r in result}


def _agents(customers):
	agents = {}
	for row in frappe.get_all(
		"Customer Agent",
		filters={"parenttype": "TP Customer", "parent": ("in", customers)},
		fields=["parent", "agent"],
		order_by="idx asc",
	):
		agents.setdefault(row.parent, []).append(frappe.utils.get_fullname(row.agent))
	return agents
