# Copyright (c) 2026, Techpark International
"""Application Wise Status: Industry Segment -> Product -> Application (the common list) -> the
customers that have it (their Technical Lead) and where each stands (its opportunity from visits).
Group rows carry their totals. Salespeople see the status
only of their own opportunities."""

import frappe
from frappe import _
from frappe.utils import flt

SHARES = (
	("share_noritake", "N"), ("share_tyrolit", "Tyrolit"), ("share_asahi", "Asahi"), ("share_tvmk", "TVMK"),
	("share_gno", "GNO"), ("share_cumi", "Cumi"), ("share_other", "Other"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data, groups = get_data(filters)
	return get_columns(), data, None, get_chart(groups), get_summary(groups)


def get_columns():
	return [
		{"fieldname": "label", "label": _("Industry / Product / Application / Customer"), "fieldtype": "Data", "width": 300},
		{"fieldname": "customers", "label": _("Customers"), "fieldtype": "Int", "width": 90},
				{"fieldname": "process", "label": _("Process"), "fieldtype": "Data", "width": 110},
		{"fieldname": "principal", "label": _("Principal"), "fieldtype": "Data", "width": 95},
		{"fieldname": "category", "label": _("Category"), "fieldtype": "Data", "width": 120},
		{"fieldname": "demand", "label": _("Annual Demand"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "quantity", "label": _("Annual Qty"), "fieldtype": "Float", "precision": 0, "width": 95},
		{"fieldname": "share", "label": _("Share"), "fieldtype": "Data", "width": 170},
		{"fieldname": "progress", "label": _("Progress"), "fieldtype": "Data", "width": 120},
		{"fieldname": "stage", "label": _("Stage"), "fieldtype": "Data", "width": 130},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 140},
		{"fieldname": "present_status", "label": _("Present Status"), "fieldtype": "Data", "width": 240},
		{"fieldname": "next_action", "label": _("Next Action"), "fieldtype": "Data", "width": 200},
		{"fieldname": "next_action_date", "label": _("Next Action By"), "fieldtype": "Date", "width": 110},
		{"fieldname": "last_visit", "label": _("Last Visit"), "fieldtype": "Date", "width": 100},
		{"fieldname": "sales_person", "label": _("Sales Person"), "fieldtype": "Data", "width": 130},
		{"fieldname": "lead", "label": _("Technical Lead"), "fieldtype": "Link", "options": "TP Technical Lead", "width": 105},
		{"fieldname": "opportunity", "label": _("Opportunity"), "fieldtype": "Link", "options": "TP Opportunity", "width": 105},
	]


def get_data(filters):
	app_filters = {}
	for field in ("industry_domain", "product"):
		if filters.get(field):
			app_filters[field] = filters[field]
	if filters.get("application"):
		app_filters["name"] = filters.application
	apps = {
		a.name: a
		for a in frappe.get_all(
			"Customer Application",
			filters=app_filters,
			fields=["name", "application_name", "industry_domain", "product", "grinding_process"],
		)
	}
	lead_filters = {"application_master": ("in", list(apps) or [""])}
	for field in ("customer", "principal", "progress"):
		if filters.get(field):
			lead_filters[field] = filters[field]
	if filters.get("stage"):
		lead_filters["stage"] = filters.stage
	leads = frappe.get_list(
		"TP Technical Lead",
		filters=lead_filters,
		fields=[
			"name", "customer", "customer_name", "application_master", "principal", "supplier_product_category",
			"grinding_process", "annual_demand_amount", "annual_quantity", "progress", "stage", "current_status",
			"opportunity", "last_visit", *[f for f, _l in SHARES],
		],
		limit_page_length=0,
	)
	# The status side comes from opportunities: get_list keeps a salesperson to their own lines
	opps = {
		o.name: o
		for o in frappe.get_list(
			"TP Opportunity",
			filters={"name": ("in", [l.opportunity for l in leads if l.opportunity] or [""])},
			fields=["name", "present_status", "next_action", "next_action_date", "sales_person", "joint_with"],
			limit_page_length=0,
		)
	}
	if filters.get("sales_person"):
		leads = [l for l in leads if (opps.get(l.opportunity) or {}).get("sales_person") == filters.sales_person]
	categories = dict(
		frappe.get_all(
			"Supplier Product Category",
			filters={"name": ("in", list({l.supplier_product_category for l in leads if l.supplier_product_category}) or [""])},
			fields=["name", "category_name"],
			as_list=True,
		)
	)
	categories = {str(k): v for k, v in categories.items()}
	products = {
		str(k): v
		for k, v in frappe.get_all(
			"Customer Product",
			filters={"name": ("in", list({a.product for a in apps.values() if a.product}) or [""])},
			fields=["name", "product_name"],
			as_list=True,
		)
	}

	by_app = {}
	for l in leads:
		by_app.setdefault(l.application_master, []).append(l)

	# Industry Segment -> Product -> Application
	tree = {}
	for app_name in by_app:
		app = apps[app_name]
		industry = app.industry_domain or _("No Industry Segment")
		product = products.get(str(app.product)) or _("No Product")
		tree.setdefault(industry, {}).setdefault(product, []).append(app_name)

	def leads_of(app_names):
		return [l for a in app_names for l in by_app[a]]

	def demand(rows):
		return sum(flt(l.annual_demand_amount) for l in rows)

	data, groups = [], []
	for industry in sorted(tree, key=lambda i: -demand(leads_of(a for p in tree[i].values() for a in p))):
		industry_key = "IND::" + industry
		data.append(_group_row(industry_key, None, 0, industry, leads_of(a for p in tree[industry].values() for a in p)))
		for product in sorted(tree[industry], key=lambda p: -demand(leads_of(tree[industry][p]))):
			product_key = f"PRD::{industry}::{product}"
			data.append(_group_row(product_key, industry_key, 1, product, leads_of(tree[industry][product])))
			for app_name in sorted(tree[industry][product], key=lambda a: (-demand(by_app[a]), apps[a].application_name)):
				app, rows = apps[app_name], by_app[app_name]
				group = _group_row(app_name, product_key, 2, app.application_name, rows)
				group.update(
					{
						"process": app.grinding_process,
						"progress": ", ".join(f"{n} {p}" for p, n in _count(l.progress for l in rows)),
					}
				)
				data.append(group)
				groups.append(group)
				for l in sorted(rows, key=lambda l: -flt(l.annual_demand_amount)):
					o = opps.get(l.opportunity) or frappe._dict()
					person = frappe.utils.get_fullname(o.sales_person) if o.sales_person else ""
					data.append(
						{
							"name": l.name,
							"parent": app_name,
							"indent": 3,
							"label": l.customer_name or l.customer,
							"principal": l.principal,
							"category": categories.get(str(l.supplier_product_category), ""),
							"process": l.grinding_process,
							"demand": flt(l.annual_demand_amount) or None,
							"quantity": flt(l.annual_quantity) or None,
							"share": "  ".join(f"{label} {round(flt(l.get(f)))}%" for f, label in SHARES if l.get(f)),
							"progress": l.progress,
							"stage": l.stage,
							"status": l.current_status,
							"present_status": " ".join((o.present_status or "").split()),
							"next_action": o.next_action,
							"next_action_date": o.next_action_date,
							"last_visit": l.last_visit,
							"sales_person": " / ".join(filter(None, [person, (o.joint_with or "").replace(", ", " / ")])),
							"lead": l.name,
							"opportunity": l.opportunity,
						}
					)
	return data, groups


def _group_row(key, parent, indent, label, rows):
	"""A group row (industry segment, product or application) with its totals."""
	dev = sum(1 for l in rows if l.stage == "Development")
	sales = sum(1 for l in rows if l.stage == "Sales")
	return {
		"name": key,
		"parent": parent,
		"indent": indent,
		"is_group": 1,
		"label": label,
		"customers": len({l.customer for l in rows}),
		"demand": sum(flt(l.annual_demand_amount) for l in rows),
		"quantity": sum(flt(l.annual_quantity) for l in rows),
		"stage": " · ".join(p for p in (f"{dev} {_('Dev')}" if dev else "", f"{sales} {_('Sales')}" if sales else "") if p),
		"_dev": dev,
		"_sales": sales,
	}


def _count(values):
	counts = {}
	for v in values:
		if v:
			counts[v] = counts.get(v, 0) + 1
	return sorted(counts.items(), key=lambda kv: -kv[1])


def get_chart(groups):
	top = sorted(groups, key=lambda g: -g["customers"])[:12]
	if not top:
		return None
	return {
		"data": {
			"labels": [g["label"] for g in top],
			"datasets": [
				{"name": _("Development"), "values": [g["_dev"] for g in top]},
				{"name": _("Sales"), "values": [g["_sales"] for g in top]},
				{"name": _("Not visited yet"), "values": [g["customers"] - g["_dev"] - g["_sales"] for g in top]},
			],
		},
		"type": "bar",
		"colors": ["#f59f00", "#228be6", "#ced4da"],
		"barOptions": {"stacked": 1, "spaceRatio": 0.35},
	}


def get_summary(groups):
	customers = sum(g["customers"] for g in groups)
	return [
		{"label": _("Applications"), "value": len(groups), "indicator": "Blue", "datatype": "Int"},
		{"label": _("Customer lines"), "value": customers, "indicator": "Blue", "datatype": "Int"},
		{"label": _("Annual Demand"), "value": sum(g["demand"] for g in groups), "indicator": "Green", "datatype": "Currency"},
	]
