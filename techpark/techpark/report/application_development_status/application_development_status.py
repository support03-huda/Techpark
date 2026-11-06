# Copyright (c) 2026, Techpark International
"""Where each development stands: one row per opportunity (customer + application / line + principal +
wheel spec), like the client's Development Status and Sales Follow-up sheets. The status is the line's
latest submitted visit (techpark/opportunity.py). Salespeople see their own opportunities."""

import frappe
from frappe import _
from frappe.utils import getdate, today

from techpark.opportunity import follow_up_state
from techpark.techpark.doctype.daily_visit_report.daily_visit_report import STAGE_PROGRESS

IMPORTANCE_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		{"fieldname": "opportunity", "label": _("Opportunity"), "fieldtype": "Link", "options": "TP Opportunity", "width": 105},
		{"fieldname": "salesperson", "label": _("Sales Person"), "fieldtype": "Data", "width": 130},
		{"fieldname": "region", "label": _("Region"), "fieldtype": "Data", "width": 100},
		{"fieldname": "customer_name", "label": _("Customer"), "fieldtype": "Data", "width": 180},
		{"fieldname": "industry", "label": _("Industry"), "fieldtype": "Data", "width": 110},
		{"fieldname": "application", "label": _("Application / Line"), "fieldtype": "Data", "width": 180},
		{"fieldname": "principal", "label": _("Principal"), "fieldtype": "Link", "options": "Principal", "width": 95},
		{"fieldname": "spec", "label": _("Wheel Spec"), "fieldtype": "Data", "width": 150},
		{"fieldname": "size", "label": _("Size"), "fieldtype": "Data", "width": 100},
		{"fieldname": "invoice_oc", "label": _("Invoice / OC"), "fieldtype": "Data", "width": 130},
		{"fieldname": "samples", "label": _("Samples"), "fieldtype": "Data", "width": 95},
		{"fieldname": "trials", "label": _("Trials"), "fieldtype": "Data", "width": 95},
		{"fieldname": "bulk_trial_po", "label": _("Bulk Trials PO"), "fieldtype": "Data", "width": 110},
		{"fieldname": "regularised", "label": _("Regularised"), "fieldtype": "Data", "width": 110},
		{"fieldname": "importance", "label": _("Importance"), "fieldtype": "Data", "width": 90},
		{"fieldname": "stage", "label": _("Stage"), "fieldtype": "Data", "width": 100},
		{"fieldname": "lead_stage", "label": _("Present Status"), "fieldtype": "Data", "width": 140},
		{"fieldname": "stage_completed", "label": _("Progress"), "fieldtype": "Percent", "width": 85},
		{"fieldname": "next_action", "label": _("Next Action"), "fieldtype": "Data", "width": 220},
		{"fieldname": "next_action_date", "label": _("Next Action By"), "fieldtype": "Date", "width": 110},
		{"fieldname": "follow_up", "label": _("Follow-up"), "fieldtype": "Data", "width": 95},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Date", "width": 100},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 65},
		{"fieldname": "lead_status", "label": _("Result"), "fieldtype": "Data", "width": 80},
		{"fieldname": "remarks", "label": _("Status / Notes"), "fieldtype": "Data", "width": 220},
		{"fieldname": "customer", "label": _("Customer Code"), "fieldtype": "Link", "options": "TP Customer", "width": 105},
		{"fieldname": "dvr", "label": _("Latest Visit"), "fieldtype": "Link", "options": "Daily Visit Report", "width": 150},
	]


def get_data(filters):
	conditions = {"visits": (">", 0)}
	for field, column in (
		("customer", "customer"), ("principal", "principal"), ("visited_by", "sales_person"),
		("stage", "stage"), ("status", "status"), ("lead_status", "lead_status"), ("importance", "importance"),
	):
		if filters.get(field):
			conditions[column] = filters[field]
	if filters.open_only:
		conditions["lead_status"] = ("not in", ("Won", "Lost"))

	# get_list applies the permissions: a salesperson sees only their own opportunities.
	opportunities = frappe.get_list(
		"TP Opportunity",
		filters=conditions,
		fields=[
			"name", "customer", "customer_name", "application", "principal", "category_name", "spec", "size",
			"importance", "sales_person", "stage", "status", "progress", "lead_status", "next_action",
			"next_action_date", "follow_up", "last_visit", "last_dvr", "visits", "remarks",
			"invoice_oc", "samples", "trials", "bulk_trial_po", "regularised",
		],
		limit_page_length=0,
	)
	customers = {
		c.name: c
		for c in frappe.get_all(
			"TP Customer",
			filters={"name": ("in", list({o.customer for o in opportunities}) or [""])},
			fields=["name", "territory_region", "industry_domain"],
		)
	}
	open_todos = set(
		frappe.get_all(
			"ToDo",
			filters={"name": ("in", [o.follow_up for o in opportunities if o.follow_up] or [""]), "status": "Open"},
			pluck="name",
		)
	)
	now = getdate(today())
	rows = []
	for o in opportunities:
		customer = customers.get(o.customer) or frappe._dict()
		rows.append(
			{
				"opportunity": o.name,
				"customer": o.customer,
				"customer_name": o.customer_name,
				"region": customer.territory_region,
				"industry": customer.industry_domain,
				"application": o.application,
				"principal": o.principal,
				"supplier_product_category": o.category_name,
				"spec": o.spec,
				"size": o.size,
				"importance": o.importance,
				"invoice_oc": o.invoice_oc,
				"samples": o.samples,
				"trials": o.trials,
				"bulk_trial_po": o.bulk_trial_po,
				"regularised": o.regularised,
				"stage": o.stage,
				"lead_stage": o.status,
				"stage_completed": o.progress or STAGE_PROGRESS.get(o.status, 0),
				"lead_status": o.lead_status,
				"last_visit": o.last_visit,
				"visits": o.visits,
				"next_action": o.next_action,
				"next_action_date": o.next_action_date,
				"follow_up": follow_up_state(o, open_todos, now),
				"salesperson": frappe.utils.get_fullname(o.sales_person) if o.sales_person else "",
				"remarks": o.remarks,
				"dvr": o.last_dvr,
			}
		)
	rows.sort(key=lambda r: (IMPORTANCE_ORDER.get(r["importance"], 3), r["customer_name"] or "", r["application"] or ""))
	return rows


def get_chart(rows):
	"""Opportunities at each status (Development then Sales)."""
	stages = [s for s in STAGE_PROGRESS if any(r["lead_stage"] == s for r in rows)]
	if not stages:
		return None
	return {
		"data": {
			"labels": stages,
			"datasets": [{"name": _("Opportunities"), "values": [sum(r["lead_stage"] == s for r in rows) for s in stages]}],
		},
		"type": "bar",
		"colors": ["#2490ef"],
	}
