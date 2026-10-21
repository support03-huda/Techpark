# Copyright (c) 2026, Techpark International
"""Customer Card: everything known about a customer in one structure.

Used by the "Customer Card" print format (jinja method get_customer_card). Link
values are resolved to their names (units, products, applications, …) so it reads naturally.
"""

import frappe
from frappe.utils import cint

# Title field of each linked master
TITLE_FIELDS = {
	"Plant": "plant_name",
	"Unit": "unit_name",
	"Customer Product": "product_name",
	"Product Category": "category_name",
	"Product Segment": "segment_name",
	"Customer Application": "application_name",
	"TP Competitor": "competitor_name",
	"Consumption Type": "comsumption_type_name",
	"Customer Department": "department_name",
}

TECHNICAL = {
	"segments": {
		"doctype": "Customer Segment Application",
		"fields": [
			"name", "address as plant", "segment", "sub_category_line", "application_notes",
			"monthly_vloume as volume", "unit", "segment_turnover_cr",
		],
		"links": {"plant": "Plant", "segment": "Product Segment", "unit": "Unit"},
	},
	"wheel_specs": {
		"doctype": "Wheel Specification",
		"fields": [
			"name", "plant", "application", "wheel_specification", "wheel_size", "wheel_speed",
			"pitch_range", "annual_consumption", "consumption_unit", "competitors", "remarks",
		],
		"links": {
			"plant": "Plant", "application": "Customer Application",
			"consumption_unit": "Unit", "competitors": "TP Competitor",
		},
	},
	"consumption": {
		"doctype": "Wheel Consumption",
		"fields": [
			"name", "plant", "consumption_type", "application", "quantity", "unit",
			"frequency", "current_supplier", "remarks",
		],
		"links": {
			"plant": "Plant", "consumption_type": "Consumption Type", "application": "Customer Application",
			"unit": "Unit", "current_supplier": "TP Competitor",
		},
	},
	"manufacturing": {
		"doctype": "Manufacturing Details",
		"fields": ["name", "plant", "manufacturing_type", "process_name", "process_type", "description", "remarks"],
		"links": {"plant": "Plant"},
	},
}


def get_customer_card(customer):
	"""Jinja method for the Customer Card print format."""
	doc = frappe.get_doc("TP Customer", customer)
	card = {key: _records(customer, cfg) for key, cfg in TECHNICAL.items()}

	plants = {str(p.record): p.plant_name for p in doc.plants if p.record}
	units = _titles("Unit", [r.unit for r in doc.production + doc.turnovers])
	products = frappe.get_all(
		"Customer Product",
		filters={"name": ("in", [r.product for r in doc.production] or [""])},
		fields=["name", "product_name", "product_category"],
	)
	categories = _titles("Product Category", [p.product_category for p in products])
	product_map = {str(p.name): p for p in products}

	card["production"] = []
	for r in doc.production:
		product = product_map.get(str(r.product)) or {}
		card["production"].append(
			{
				"product": product.get("product_name") or r.product,
				"category": _title(categories, product.get("product_category")),
				"plant": _title(plants, r.plant),
				"volume": r.production_volume,
				"unit": _title(units, r.unit),
				"frequency": r.frequency,
			}
		)
	card["turnovers"] = [
		{
			"financial_year": r.financial_year,
			"plant": _title(plants, r.plant),
			"amount": r.amount,
			"unit": _title(units, r.unit),
			"frequency": r.get("frequency"),
			"remarks": r.remarks,
		}
		for r in doc.turnovers
	]
	card["contacts"] = [c for c in doc.contacts if cint(c.is_active)]
	card["machines"] = [{**m.as_dict(), "plant": _title(plants, m.plant)} for m in doc.machines]
	card["agents"] = [frappe.utils.get_fullname(a.agent) for a in doc.handled_by]
	card["principals"] = [p.principal for p in doc.principals]
	return card


def _records(customer, cfg):
	rows = frappe.get_all(cfg["doctype"], filters={"customer": customer}, fields=cfg["fields"], order_by="creation asc")
	for field, doctype in cfg["links"].items():
		titles = _titles(doctype, [r.get(field) for r in rows])
		for r in rows:
			r[field + "_title"] = _title(titles, r.get(field))
	if cfg["doctype"] == "Customer Segment Application":
		_add_segment_children(rows)
	return rows


def _add_segment_children(rows):
	"""Applications and competitors of each segment (Table MultiSelect children)."""
	names = [r.name for r in rows] or [""]
	children = {}
	for child, field, doctype in (
		("Customer Application S", "application_name", "Customer Application"),
		("Competitor S", "competitor_name", "TP Competitor"),
	):
		items = frappe.get_all(child, filters={"parent": ("in", names)}, fields=["parent", field], order_by="idx asc")
		titles = _titles(doctype, [i.get(field) for i in items])
		children[child] = items, field, titles
	for r in rows:
		apps, app_field, app_titles = children["Customer Application S"]
		comps, comp_field, comp_titles = children["Competitor S"]
		r["applications"] = ", ".join(_title(app_titles, i[app_field]) for i in apps if i.parent == r.name)
		r["competitors"] = ", ".join(_title(comp_titles, i[comp_field]) for i in comps if i.parent == r.name)


def _titles(doctype, names):
	names = list({n for n in names if n})
	if not names:
		return {}
	title_field = TITLE_FIELDS[doctype]
	return {
		str(r.name): r.get(title_field) or str(r.name)
		for r in frappe.get_all(doctype, filters={"name": ("in", names)}, fields=["name", title_field])
	}


def _title(titles, value):
	"""Name of a linked record; autoincrement masters come back as ints, so compare as text."""
	if value in (None, ""):
		return ""
	return titles.get(str(value), str(value))
