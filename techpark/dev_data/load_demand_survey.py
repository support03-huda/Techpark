# Copyright (c) 2026, Techpark International
"""Load the client's Demand Survey sheet (DVR_CRM_Expense Formats.xlsx) as Technical Leads.

	bench --site techpark.local execute techpark.dev_data.load_demand_survey.execute

Safe to run again: customers are matched by name and a lead that already exists for the
customer (same application + process + category + wheel size) is skipped.
"""

import json

import frappe
from frappe.utils import cstr

LEAD_FIELDS = (
	"application", "grinding_process", "production_line", "distribution_channel", "contact_person", "progress",
	"annual_demand_amount", "annual_quantity", "unit_price",
	"share_noritake", "share_tyrolit", "share_asahi", "share_tvmk", "share_gno", "share_cumi", "share_other",
	"other_competitors", "machine_maker", "machine_quantity", "wheel_speed",
	"size_od", "size_t", "size_id", "x_layer", "issue", "action_plan", "remarks",
)


def execute():
	with open(frappe.get_app_path("techpark", "dev_data", "demand_survey.json")) as f:
		data = json.load(f)

	principal = _principal()
	count = {"customers created": 0, "customers found": 0, "leads created": 0, "leads skipped": 0}
	for entry in data:
		customer = _customer(entry, principal, count)
		existing = {
			(cstr(r.application), cstr(r.grinding_process), cstr(r.supplier_product_category), cstr(r.size_od), cstr(r.size_t))
			for r in frappe.get_all(
				"TP Technical Lead",
				filters={"customer": customer},
				fields=["application", "grinding_process", "supplier_product_category", "size_od", "size_t"],
			)
		}
		for row in entry["leads"]:
			category = _category(principal, row.get("category"))
			key = (
				cstr(row.get("application")), cstr(row.get("grinding_process")), cstr(category),
				cstr(row.get("size_od")), cstr(row.get("size_t")),
			)
			if key in existing:
				count["leads skipped"] += 1
				continue
			values = {f: row[f] for f in LEAD_FIELDS if row.get(f) not in (None, "")}
			product = _product(row.get("product_text"))
			if product:
				values["product"] = product
			elif row.get("product_text"):
				values["production_line"] = " / ".join(filter(None, [row["product_text"], row.get("production_line")]))
			frappe.get_doc(
				{
					"doctype": "TP Technical Lead",
					"customer": customer,
					"principal": principal,
					"supplier_product_category": category,
					**values,
				}
			).insert(ignore_permissions=True)
			existing.add(key)
			count["leads created"] += 1
	frappe.db.commit()
	print(count)


def _principal():
	name = frappe.db.get_value("Principal", {"principal_name": ("like", "%noritake%")})
	if name:
		return name
	return frappe.get_doc({"doctype": "Principal", "principal_name": "Noritake", "is_active": 1}).insert(
		ignore_permissions=True
	).name


def _category(principal, category_name):
	if not category_name:
		return None
	name = frappe.db.get_value(
		"Supplier Product Category", {"principal": principal, "category_name": category_name}
	)
	if name:
		return name
	return frappe.get_doc(
		{"doctype": "Supplier Product Category", "principal": principal, "category_name": category_name, "is_active": 1}
	).insert(ignore_permissions=True).name


def _product(product_name):
	if not product_name:
		return None
	return frappe.db.get_value("Customer Product", {"product_name": product_name})


def _customer(entry, principal, count):
	name = frappe.db.get_value("TP Customer", {"customer_name": entry["customer_name"]})
	if name:
		count["customers found"] += 1
		return name
	industry = (
		frappe.db.get_value("Industry Domain", {"industry_name": entry.get("industry")}) if entry.get("industry") else None
	)
	doc = frappe.get_doc(
		{
			"doctype": "TP Customer",
			"customer_name": entry["customer_name"],
			"customer_type": "Company",
			"customer_status": "Active Customer",
			"plant_location": entry.get("location"),
			"state": entry.get("state"),
			"industry_domain": industry,
			"principals": [{"principal": principal}],
		}
	)
	doc.insert(ignore_permissions=True)
	count["customers created"] += 1
	return doc.name
