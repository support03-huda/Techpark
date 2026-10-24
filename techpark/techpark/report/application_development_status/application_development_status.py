# Copyright (c) 2026, Techpark International
"""Where each application stands: one row per customer, segment / line application,
principal and product category, taken from its latest Visit Report. Salespeople see
only their own visits (DVR permissions)."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

from techpark.techpark.doctype.daily_visit_report.daily_visit_report import STAGE_PROGRESS

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
		{"fieldname": "lead_stage", "label": _("Stage"), "fieldtype": "Data", "width": 150},
		{"fieldname": "stage_completed", "label": _("Progress"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "lead_status", "label": _("Lead Status"), "fieldtype": "Data", "width": 95},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Date", "width": 100},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 65},
		{"fieldname": "next_action", "label": _("Next Action"), "fieldtype": "Data", "width": 220},
		{"fieldname": "next_action_date", "label": _("Next Action By"), "fieldtype": "Date", "width": 110},
		{"fieldname": "follow_up", "label": _("Follow-up"), "fieldtype": "Data", "width": 95},
		{"fieldname": "salesperson", "label": _("Salesperson"), "fieldtype": "Data", "width": 140},
		{"fieldname": "dvr", "label": _("Latest Visit"), "fieldtype": "Link", "options": "Daily Visit Report", "width": 150},
	]


def get_data(filters):
	conditions = {"docstatus": ("<", 2)}
	for field in ("customer", "principal", "visited_by"):
		if filters.get(field):
			conditions[field] = filters[field]

	# get_list applies the DVR permissions, so a salesperson sees only their own visits.
	visits = frappe.get_list(
		"Daily Visit Report",
		filters=conditions,
		fields=[
			"name", "customer", "customer_name", "segment_application", "plant_name", "principal",
			"supplier_product_category", "lead_stage", "lead_status", "visit_date", "next_action",
			"next_action_date", "visited_by", "follow_up",
		],
		order_by="visit_date desc, creation desc",
		limit_page_length=0,
	)

	latest, counts = {}, {}
	for v in visits:
		key = (v.customer, v.segment_application or v.plant_name, v.principal, v.supplier_product_category)
		counts[key] = counts.get(key, 0) + 1
		latest.setdefault(key, v)

	lines = application_names({v.segment_application for v in latest.values() if v.segment_application})
	open_todos = set(
		frappe.get_all(
			"ToDo",
			filters={"name": ("in", [v.follow_up for v in latest.values() if v.follow_up] or [""]), "status": "Open"},
			pluck="name",
		)
	)

	rows = []
	for key, v in latest.items():
		status = v.lead_status
		if filters.lead_status and status != filters.lead_status:
			continue
		if filters.open_only and status in ("Won", "Lost"):
			continue
		stage = "Order Received" if status == "Won" else v.lead_stage
		rows.append(
			{
				"customer": v.customer,
				"customer_name": v.customer_name,
				"application": lines.get(v.segment_application) or "",
				"plant_name": v.plant_name,
				"principal": v.principal,
				"supplier_product_category": v.supplier_product_category,
				"lead_stage": stage,
				"stage_completed": STAGE_PROGRESS.get(stage, 0),
				"lead_status": status,
				"last_visit": v.visit_date,
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
	"""Applications at each stage (latest stage only, so one lead counts once)."""
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
