# Copyright (c) 2026, Techpark International
"""Load the rest of the client's sheet (DVR_CRM_Expense Formats.xlsx) on the dev site:

- Sales Follow-up matters -> customers (with region), and per application line a submitted visit
  (DVR) at the line's present status, so each line becomes a TP Opportunity with its next action.
- Customer Card Format 1 -> Products Info: products & production volume, turnover, abrasive consumption.
- Customer Card Format 2 -> JIS Tools: company profile, machine details, current wheel usage.

	bench --site techpark.local execute techpark.dev_data.load_customer_sheets.execute

Safe to run again: customers are matched by name, a sheet row that already has its visit is skipped,
and products / machines / wheels already on a customer are not added twice.
"""

import json

import frappe
from frappe.utils import add_days, cstr, today

PRINCIPAL_HINT = "noritake"  # the sheet is "NORITAKE Follow-up matters"
COUNT = {}


def bump(key, n=1):
	COUNT[key] = COUNT.get(key, 0) + n


def execute():
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	with open(frappe.get_app_path("techpark", "dev_data", "customer_sheets.json")) as f:
		data = json.load(f)
	principal = _principal()
	try:
		for row in data["follow_up"]:
			_safe(f"follow-up row {row['sheet_row']}", _follow_up, row, principal)
		for card in data["products"]:
			_safe(f"products {card['customer']}", _products, card)
		_safe("JIS Tools", _jis, data["jis"])
	finally:
		frappe.flags.mute_emails = False
	frappe.db.commit()
	print("\n".join(f"{k}: {v}" for k, v in sorted(COUNT.items())))


def _safe(label, fn, *args):
	frappe.db.savepoint("sheet_row")
	try:
		fn(*args)
	except Exception as e:  # noqa: BLE001 - report and carry on with the next row
		frappe.db.rollback(save_point="sheet_row")
		frappe.clear_messages()
		bump("errors")
		print(f"ERROR {label}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# masters
def _principal():
	return frappe.db.get_value("Principal", {"principal_name": ("like", f"%{PRINCIPAL_HINT}%")}) or frappe.get_doc(
		{"doctype": "Principal", "principal_name": "Noritake", "is_active": 1}
	).insert(ignore_permissions=True).name


def _master(doctype, field, value, **extra):
	if not value:
		return None
	name = frappe.db.get_value(doctype, {field: value})
	if name:
		return name
	bump(f"new {doctype}")
	return frappe.get_doc({"doctype": doctype, field: value, **extra}).insert(ignore_permissions=True).name


def _region(region):
	if not region:
		return None
	return _master("Territory Region", "region_name", region, zone=region.split(" ")[0], is_active=1)


def _customer(name, region=None, industry=None):
	existing = frappe.db.get_value("TP Customer", {"customer_name": name})
	if existing:
		if region and not frappe.db.get_value("TP Customer", existing, "territory_region"):
			frappe.db.set_value("TP Customer", existing, "territory_region", _region(region))
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "TP Customer",
			"customer_name": name,
			"customer_type": "Company",
			"customer_status": "Active Customer",
			"territory_region": _region(region),
			"industry_domain": frappe.db.get_value("Industry Domain", {"industry_name": industry}) if industry else None,
		}
	).insert(ignore_permissions=True)
	bump("customers created")
	return doc.name


# ---------------------------------------------------------------------------
# Sales Follow-up matters
def _status(present, next_action):
	"""(stage, development status, sales status) from the sheet's free-text Present Status."""
	t, n = cstr(present).lower(), cstr(next_action).lower()
	if any(w in t for w in ("regularised", "regularly", "regulally", "regularized")):
		return "Sales", None, "Regularization"
	if "payment" in n and "fail" not in t:
		return "Sales", None, "Payment Follow-up"
	if any(w in t for w in ("po no", "order received", "order recd")):
		return "Sales", None, "Bulk Trial PO"
	if any(w in t for w in ("failed", "did not perform", "fail")):
		return "Development", "Trial Failed", None
	if any(w in t for w in ("sucess", "success", "successfully")):
		return "Development", "Successful Trial", None
	if any(w in t for w in ("trial pending", "trail", "under trial", "trial wheel")):
		return "Development", "Trial in Progress", None
	if any(w in t for w in ("supplied", "received", "dispatched", "despatched", "delivered")):
		return "Development", "Sample Received", None
	if any(w in t for w in ("quot", "offer", "proposal", "pi sent")) or "offer submitted" in n:
		return "Development", "Offer Submitted", None
	if "enquiry" in t:
		return "Development", "Enquiry Received", None
	return "Development", "Introduction", None


def _follow_up(row, principal):
	customer = _customer(row["customer"], row.get("region"), row.get("industry"))
	if not row.get("application"):
		bump("follow-up rows without application (customer only)")
		return
	marker = f"[Sales Follow-up sheet row {row['sheet_row']}]"
	if frappe.db.exists("Daily Visit Report", {"customer": customer, "discussion_notes": ("like", f"{marker}%")}):
		bump("follow-up visits already loaded")
		return

	lead = frappe.db.get_value(
		"TP Technical Lead", {"customer": customer, "principal": principal, "application": row["application"]}
	) or frappe.get_doc(
		{"doctype": "TP Technical Lead", "customer": customer, "principal": principal, "application": row["application"]}
	).insert(ignore_permissions=True).name

	stage, development, sales = _status(row.get("present_status"), row.get("next_action"))
	notes = [marker, f"Sales person: {row.get('sales_person') or '-'} ({row.get('region') or '-'})"]
	if row.get("present_status"):
		notes.append(f"Present status: {row['present_status']}")
	dvr = frappe.get_doc(
		{
			"doctype": "Daily Visit Report",
			"visit_date": today(),
			"customer": customer,
			"dvr_type": "Visit",
			"dvr_stage": stage,
			"visited_by": "Administrator",
			"principal": principal,
			"technical_lead": lead,
			"development_status": development,
			"sales_status": sales,
			"discussion_notes": "\n".join(notes),
			"next_action": row.get("next_action") or None,
			"next_action_date": add_days(today(), 7) if row.get("next_action") else None,
		}
	)
	try:
		dvr.insert(ignore_permissions=True)
	except frappe.ValidationError:
		# The line already went past development on an earlier visit: record it as a Sales visit.
		frappe.clear_messages()
		dvr = frappe.copy_doc(dvr)
		dvr.update({"dvr_stage": "Sales", "development_status": None, "sales_status": sales or "Enquiry Follow-up"})
		dvr.insert(ignore_permissions=True)
	dvr.submit()
	bump(f"follow-up visits ({stage})")


# ---------------------------------------------------------------------------
# Customer Card Format 1
def _products(card):
	name = _customer(card["customer"])
	doc = frappe.get_doc("TP Customer", name)
	for field in ("annual_turnover_cr", "group_turnover_cr", "abrasive_consumption_cr", "abrasive_consumption_details"):
		if card.get(field) and not doc.get(field):
			doc.set(field, card[field])
	have = {cstr(r.product) for r in doc.production}
	for p in card["products"]:
		product = _master("Customer Product", "product_name", p["product"], active=1)
		if cstr(product) in have:
			continue
		doc.append(
			"production",
			{
				"product": product,
				"production_volume": p.get("production_volume"),
				"unit": _master("Unit", "unit_name", p.get("unit"), active=1),
				"frequency": p.get("frequency") or "Monthly",
				"remarks": p.get("remarks") or None,
			},
		)
		have.add(cstr(product))
		bump("product rows added")
	doc.save(ignore_permissions=True)
	bump("Customer Card 1 customers updated")


# ---------------------------------------------------------------------------
# Customer Card Format 2
def _jis(card):
	doc = frappe.get_doc("TP Customer", _customer(card["customer"]))
	for field in ("established_year", "manufacturing_profile", "heat_treatment"):
		if card.get(field) and not doc.get(field):
			doc.set(field, card[field])
	have_machines = {cstr(m.machine_type) for m in doc.machines}
	for m in card["machines"]:
		if m["machine_type"] not in have_machines:
			doc.append("machines", m)
			bump("machine rows added")
	have_wheels = {(cstr(w.wheel_specification), cstr(w.pitch_range)) for w in doc.wheel_specs}
	for w in card["wheels"]:
		if (w["wheel_specification"], w["pitch_range"]) in have_wheels:
			continue
		doc.append(
			"wheel_specs",
			{
				**w,
				"application": _master("Customer Application", "application_name", w["application"], is_active=1),
				"consumption_unit": _master("Unit", "unit_name", w["consumption_unit"], active=1),
			},
		)
		bump("wheel usage rows added")
	doc.save(ignore_permissions=True)
	bump("Customer Card 2 customers updated")
