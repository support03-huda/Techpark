# Copyright (c) 2026, Techpark International
"""Where each application stands, principal-wise: one row per customer, segment / line application,
principal and product category, taken from its latest principal row on a Visit Report (Development
stage up to the Successful Trial, then the Sales stage). Salespeople see only their own visits
(DVR permissions)."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

from techpark.techpark.doctype.daily_visit_report.daily_visit_report import (
	LOST_STATUSES,
	STAGE_PROGRESS,
	WON_STATUSES,
)

# Follow-up due within this many days counts as "Due Soon".
DUE_SOON_DAYS = 3


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		{"fieldname": "customer", "label": _("Customer Code"), "fieldtype": "Link", "options": "TP Customer", "width": 105},
		{"fieldname": "customer_name", "label": _("Customer"), "fieldtype": "Data", "width": 190},
		{"fieldname": "application", "label": _("Application / Line"), "fieldtype": "Data", "width": 190},
		{"fieldname": "plant_name", "label": _("Plant"), "fieldtype": "Data", "width": 120},
		{"fieldname": "principal", "label": _("Principal"), "fieldtype": "Link", "options": "Principal", "width": 100},
		{"fieldname": "supplier_product_category", "label": _("Product Category"), "fieldtype": "Data", "width": 160},
		{"fieldname": "stage", "label": _("Stage"), "fieldtype": "Data", "width": 100},
		{"fieldname": "lead_stage", "label": _("Status"), "fieldtype": "Data", "width": 150},
		{"fieldname": "stage_completed", "label": _("Progress"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "lead_status", "label": _("Lead Status"), "fieldtype": "Data", "width": 95},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Date", "width": 100},
		{"fieldname": "dvr_type", "label": _("Last Contact"), "fieldtype": "Data", "width": 100},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 65},
		{"fieldname": "next_action", "label": _("Next Action"), "fieldtype": "Data", "width": 220},
		{"fieldname": "next_action_date", "label": _("Next Action By"), "fieldtype": "Date", "width": 110},
		{"fieldname": "follow_up", "label": _("Follow-up"), "fieldtype": "Data", "width": 95},
		{"fieldname": "salesperson", "label": _("Salesperson"), "fieldtype": "Data", "width": 140},
		{"fieldname": "dvr", "label": _("Latest Visit"), "fieldtype": "Link", "options": "Daily Visit Report", "width": 150},
	]


def row_lead_status(status):
	if status in WON_STATUSES:
		return "Won"
	if status in LOST_STATUSES:
		return "Lost"
	return "On Hold" if status == "On Hold" else "Prospect"


def get_data(filters):
	conditions = {"docstatus": ("<", 2)}
	for field in ("customer", "visited_by", "department"):
		if filters.get(field):
			conditions[field] = filters[field]

	# get_list applies the DVR permissions, so a salesperson sees only their own visits.
	visits = {
		v.name: v
		for v in frappe.get_list(
			"Daily Visit Report",
			filters=conditions,
			fields=[
				"name", "customer", "customer_name", "segment_application", "plant_name", "visit_date", "dvr_type",
				"next_action", "next_action_date", "visited_by", "follow_up", "creation",
			],
			limit_page_length=0,
		)
	}
	row_filters = {"parenttype": "Daily Visit Report", "parent": ("in", list(visits) or [""])}
	if filters.get("principal"):
		row_filters["principal"] = filters.principal
	principal_rows = frappe.get_all(
		"DVR Principal",
		filters=row_filters,
		fields=["parent", "principal", "supplier_product_category", "stage", "development_status", "sales_status", "progress"],
	)
	# Newest visit first, so the first row seen per application is its latest.
	principal_rows.sort(key=lambda r: (visits[r.parent].visit_date, visits[r.parent].creation), reverse=True)

	latest, counts = {}, {}
	for r in principal_rows:
		v = visits[r.parent]
		key = (v.customer, v.segment_application or v.plant_name, r.principal, r.supplier_product_category)
		counts[key] = counts.get(key, 0) + 1
		latest.setdefault(key, (v, r))

	lines = application_names({v.segment_application for v, r in latest.values() if v.segment_application})
	open_todos = set(
		frappe.get_all(
			"ToDo",
			filters={"name": ("in", [v.follow_up for v, r in latest.values() if v.follow_up] or [""]), "status": "Open"},
			pluck="name",
		)
	)

	rows = []
	for key, (v, r) in latest.items():
		status = (r.stage == "Sales" and r.sales_status) or r.development_status
		lead_status = row_lead_status(status)
		if filters.lead_status and lead_status != filters.lead_status:
			continue
		if filters.stage and r.stage != filters.stage:
			continue
		if filters.open_only and lead_status in ("Won", "Lost"):
			continue
		rows.append(
			{
				"customer": v.customer,
				"customer_name": v.customer_name,
				"application": lines.get(v.segment_application) or "",
				"plant_name": v.plant_name,
				"principal": r.principal,
				"supplier_product_category": r.supplier_product_category,
				"stage": r.stage,
				"lead_stage": status,
				"stage_completed": r.progress or STAGE_PROGRESS.get(status, 0),
				"lead_status": lead_status,
				"last_visit": v.visit_date,
				"dvr_type": v.dvr_type,
				"visits": counts[key],
				"next_action": v.next_action,
				"next_action_date": v.next_action_date,
				"follow_up": follow_up_state(v, open_todos),
				"salesperson": frappe.utils.get_fullname(v.visited_by) if v.visited_by else "",
				"dvr": v.name,
			}
		)
	rows.sort(key=lambda r: (r["customer_name"] or "", r["application"], r["principal"] or ""))
	return rows


def follow_up_state(visit, open_todos):
	"""Overdue / Due Soon / Planned while the follow-up is open; empty when done or none."""
	if not visit.next_action_date or (visit.follow_up and visit.follow_up not in open_todos):
		return ""
	days = date_diff(getdate(visit.next_action_date), today())
	if days < 0:
		return _("Overdue")
	return _("Due Soon") if days <= DUE_SOON_DAYS else _("Planned")


def application_names(names):
	"""Segment / line application -> "Segment – Line"."""
	if not names:
		return {}
	result = {}
	for s in frappe.get_all(
		"Customer Segment Application",
		filters={"name": ("in", list(names))},
		fields=["name", "segment", "sub_category_line"],
	):
		segment = frappe.db.get_value("Product Segment", s.segment, "segment_name") if s.segment else ""
		result[s.name] = " – ".join(p for p in (segment, s.sub_category_line) if p) or s.name
	return result


def get_chart(rows):
	"""Applications at each status (latest status only, so one lead counts once), Development then Sales."""
	stages = [s for s in STAGE_PROGRESS if any(r["lead_stage"] == s for r in rows)]
	if not stages:
		return None
	return {
		"data": {
			"labels": stages,
			"datasets": [{"name": _("Applications"), "values": [sum(r["lead_stage"] == s for r in rows) for s in stages]}],
		},
		"type": "bar",
		"colors": ["#2490ef"],
	}
