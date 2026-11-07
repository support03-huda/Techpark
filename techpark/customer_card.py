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

def get_customer_card(customer):
	"""Jinja method for the Customer Card print format."""
	doc = frappe.get_doc("TP Customer", customer)
	card = {}

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
	card["agents"] = [frappe.utils.get_fullname(a.agent) for a in doc.handled_by]
	card["principals"] = [p.principal for p in doc.principals]
	return card


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
