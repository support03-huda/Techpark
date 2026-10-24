# Copyright (c) 2026, Techpark International
"""Wipe all TechPark data on a site and load demo data (5 fictional customers).

DESTRUCTIVE. Take a backup first, then run on the server:

	bench --site techpark.local backup
	bench --site techpark.local execute techpark.demo_data.reset_and_load --kwargs "{'confirm': 'DELETE'}"

Deletes every record of every TechPark DocType (customers, contacts, plants, visits,
technical records and the TechPark masters) plus their ToDos, comments,
versions and attachments. Dashboards, reports, workspaces and users are not touched.
All company names below are fictional.
"""

import frappe
from frappe.utils import add_days, today

from techpark.install import seed_principals, seed_regions

# Naming-series prefixes of TechPark DocTypes, reset so codes start again from 1
SERIES_PREFIXES = ["DVR-", "CON-", "SEG", "CSA-", "CPP-", "CTO-", "WCN-", "WSP-", "MFD-", "CAP-", "DEPT-", "CDV-", "U-"]


def reset_and_load(confirm=None):
	if confirm != "DELETE":
		frappe.throw("This deletes ALL TechPark data. Run again with --kwargs \"{'confirm': 'DELETE'}\".")
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	print(f"Site: {frappe.local.site}")

	wipe()
	masters = load_masters()
	users = sales_users()
	for spec in CUSTOMERS:
		load_customer(spec, masters, users)

	frappe.db.commit()
	print("Done:", {dt: frappe.db.count(dt) for dt in ("TP Customer", "Customer Contact", "Plant", "Daily Visit Report")})


# ---------------------------------------------------------------------------
# Wipe
# ---------------------------------------------------------------------------


def wipe():
	doctypes = frappe.get_all("DocType", filters={"module": "TechPark", "issingle": 0, "is_virtual": 0}, pluck="name")
	parents = [d for d in doctypes if not frappe.get_meta(d).istable]

	for name in frappe.get_all("File", filters={"attached_to_doctype": ("in", parents)}, pluck="name"):
		frappe.delete_doc("File", name, force=True, ignore_permissions=True)
	for doctype, field in (
		("ToDo", "reference_type"),
		("Comment", "reference_doctype"),
		("Version", "ref_doctype"),
		("Communication", "reference_doctype"),
		("Notification Log", "document_type"),
	):
		frappe.db.delete(doctype, {field: ("in", parents)})

	for doctype in doctypes:
		frappe.db.delete(doctype)
		print(f"  cleared {doctype}")

	for prefix in SERIES_PREFIXES:
		frappe.db.sql("delete from `tabSeries` where name like %s", (prefix + "%",))
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Masters
# ---------------------------------------------------------------------------


def _master(doctype, title_field, title, **extra):
	doc = frappe.get_doc({"doctype": doctype, title_field: title, **extra}).insert(ignore_permissions=True)
	return doc.name


def load_masters():
	seed_principals()
	seed_regions()
	for category in ("Grinding Stone (Vitrified)",):  # Everloy / ALMT examples
		pass
	_master("Supplier Product Category", "category_name", "Carbide Products", principal="Everloy")
	_master("Supplier Product Category", "category_name", "Tungsten / Molybdenum Products", principal="ALMT")

	m = frappe._dict()
	m.unit = {u: _master("Unit", "unit_name", u, active=1) for u in ("Lakh Pieces", "Pieces", "Tons", "Crore")}
	m.category = {
		c: _master("Product Category", "category_name", c, is_active=1) for c in ("Bearings", "Rolling Elements", "Flat Products", "Cutting Tools")
	}
	m.segment = {
		s: _master("Product Segment", "segment_name", s, is_active=1)
		for s in ("Bearings", "Balls & Rollers", "Steel", "Foil", "Cutting Tools")
	}
	m.product = {
		name: _master("Customer Product", "product_name", name, product_category=m.category[cat], segment=m.segment[seg], active=1)
		for name, cat, seg in (
			("Ball Bearings", "Bearings", "Bearings"),
			("Taper Roller Bearings", "Bearings", "Bearings"),
			("Hub Bearings", "Bearings", "Bearings"),
			("Cylindrical Rollers", "Rolling Elements", "Balls & Rollers"),
			("Steel Balls", "Rolling Elements", "Balls & Rollers"),
			("Aluminium Foil", "Flat Products", "Foil"),
			("Thread Rolling Dies", "Cutting Tools", "Cutting Tools"),
		)
	}
	m.competitor = {c: _master("TP Competitor", "competitor_name", c, is_active=1) for c in ("Tyrolit", "GNO", "Cumi", "Asahi", "TVMK")}
	m.consumption = {
		c: _master("Consumption Type", "comsumption_type_name", c, is_active=1) for c in ("Abrasive Wheel", "Honing Stone", "Dresser")
	}
	m.department = {
		d: _master("Customer Department", "department_name", d, is_active=1) for d in ("Production", "Purchase", "Quality")
	}
	m.application = {
		a: _master("Customer Application", "application_name", a, is_active=1)
		for a in ("OD Grinding", "ID Bore Grinding", "Track Grinding", "Centerless Grinding", "Roll Grinding", "Ball Lapping", "Thread Grinding")
	}
	m.category_of = {
		c.category_name: c.name
		for c in frappe.get_all("Supplier Product Category", fields=["name", "category_name"])
	}
	return m


def sales_users():
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ("not in", ["Administrator", "Guest"])},
		pluck="name",
		limit=3,
	)
	return users or ["Administrator"]


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


def load_customer(spec, m, users):
	agents = users[: spec.get("agents", 1)]
	customer = frappe.get_doc(
		{
			"doctype": "TP Customer",
			"customer_name": spec["name"],
			"group_name": spec.get("group"),
			"industry_domain": spec["industry"],
			"customer_status": spec["status"],
			"territory_region": spec["region"],
			"annual_turnover_cr": spec["turnover"],
			"group_turnover_cr": spec.get("group_turnover"),
			"total_employees": spec["employees"],
			"established_year": spec["established"],
			"customer_address": spec["plants"][0]["plant_address"],
			"plant_location": spec["plants"][0]["plant_location"],
			"state": spec["plants"][0]["state"],
			"pincode": spec["plants"][0]["pincode"],
			"segments": [{"segment": m.segment[s]} for s in spec["segments"]],
			"principals": [{"principal": p} for p in spec["principals"]],
			"handled_by": [{"agent": a} for a in agents],
			"contacts": [dict(c, is_active=1) for c in spec["contacts"]],
			"plants": [dict(p, country="India", is_active=1) for p in spec["plants"]],
			"machines": spec["machines"],
		}
	).insert(ignore_permissions=True)

	# Production / turnover rows need the plant codes created on the first save
	plant = {p.plant_name: p.record for p in customer.plants}
	for product, plant_name, qty, unit in spec["production"]:
		customer.append(
			"production",
			{"plant": plant[plant_name], "product": m.product[product], "production_volume": qty, "unit": m.unit[unit],
			 "frequency": "Monthly", "department": m.department["Production"]},
		)
	for fy, amount, remarks in spec["turnovers"]:
		customer.append("turnovers", {"financial_year": fy, "amount": amount, "unit": m.unit["Crore"], "frequency": "Annual", "remarks": remarks})
	customer.save(ignore_permissions=True)

	main_plant = customer.plants[0].record
	tech = spec["technical"]
	frappe.get_doc(
		{
			"doctype": "Customer Segment Application",
			"customer": customer.name,
			"address": main_plant,
			"segment": m.segment[spec["segments"][0]],
			"sub_category_line": tech["line"],
			"department": m.department["Production"],
			"applications": [{"application_name": m.application[a]} for a in tech["applications"]],
			"monthly_vloume": tech["volume"],
			"unit": m.unit[tech["volume_unit"]],
			"segment_turnover_cr": tech["segment_turnover"],
			"competitors_on_line": [{"competitor_name": m.competitor[c]} for c in tech["competitors"]],
		}
	).insert(ignore_permissions=True)
	for w in tech["wheels"]:
		frappe.get_doc(
			{
				"doctype": "Wheel Specification",
				"customer": customer.name,
				"plant": main_plant,
				"application": m.application[tech["applications"][0]],
				"segment": m.segment[spec["segments"][0]],
				"wheel_specification": w[0],
				"wheel_size": w[1],
				"wheel_speed": w[2],
				"pitch_range": w[3],
				"annual_consumption": w[4],
				"consumption_unit": m.unit["Pieces"],
				"competitors": m.competitor[tech["competitors"][0]],
			}
		).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Wheel Consumption",
			"customer": customer.name,
			"plant": main_plant,
			"consumption_type": m.consumption[tech["consumption"][0]],
			"application": m.application[tech["applications"][0]],
			"quantity": tech["consumption"][1],
			"unit": m.unit["Pieces"],
			"frequency": "Yearly",
			"current_supplier": m.competitor[tech["competitors"][0]],
		}
	).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Manufacturing Details",
			"customer": customer.name,
			"plant": main_plant,
			"manufacturing_type": tech["manufacturing"][0],
			"process_name": tech["manufacturing"][1],
			"process_type": tech["manufacturing"][2],
			"description": tech["manufacturing"][3],
		}
	).insert(ignore_permissions=True)

	primary = next(c for c in spec["contacts"] if c.get("is_primary"))
	contact_label = f"{primary['person_name']} ({primary['designation']})"
	for i, v in enumerate(spec["visits"]):
		dvr = frappe.get_doc(
			{
				"doctype": "Daily Visit Report",
				"visit_date": add_days(today(), -v["days_ago"]),
				"visit_time": "11:00:00",
				"customer": customer.name,
				"plant": main_plant,
				"contact_person": contact_label,
				"visit_purpose": v["purpose"],
				"visited_by": agents[i % len(agents)],
				"principal": v["principal"],
				"supplier_product_category": m.category_of.get(v.get("category")),
				"application_potentials": v.get("potential"),
				"competitor_line_activity": v.get("competition"),
				"lead_status": v["status"],
				"lead_stage": v["stage"],
				"discussion_notes": v["notes"],
				"next_action": v.get("next_action"),
				"next_action_date": add_days(today(), v["next_in"]) if v.get("next_action") else None,
			}
		).insert(ignore_permissions=True)
		dvr.submit()
	print(f"  loaded {customer.name} {customer.customer_name}")


# ---------------------------------------------------------------------------
# Demo customers (fictional)
# ---------------------------------------------------------------------------

CUSTOMERS = [
	{
		"name": "Apex Bearings Ltd.",
		"group": "Apex Group",
		"industry": "Automotive & Industrial",
		"status": "Active Customer",
		"region": "West - MH",
		"turnover": 2100,
		"group_turnover": 4800,
		"employees": 2400,
		"established": 1965,
		"agents": 2,
		"segments": ["Bearings"],
		"principals": ["Noritake"],
		"contacts": [
			{"person_name": "Rahul Deshmukh", "designation": "Purchase Manager", "department": "Purchase", "phone": "+91 98220 11001", "email": "rahul.deshmukh@apexbearings.example", "is_primary": 1},
			{"person_name": "Sneha Kulkarni", "designation": "Production Head", "department": "Production", "phone": "+91 98220 11002", "notes": "Available after 3 pm"},
		],
		"plants": [
			{"plant_name": "Apex Chakan Plant", "plant_location": "Chakan, Pune", "state": "Maharashtra", "pincode": "410501", "plant_address": "Plot 21, MIDC Phase II, Chakan, Pune"},
			{"plant_name": "Apex Nashik Plant", "plant_location": "Nashik", "state": "Maharashtra", "pincode": "422010", "plant_address": "D-4, MIDC Satpur, Nashik"},
		],
		"production": [
			("Ball Bearings", "Apex Chakan Plant", 19.7, "Lakh Pieces"),
			("Taper Roller Bearings", "Apex Chakan Plant", 13.5, "Lakh Pieces"),
			("Hub Bearings", "Apex Nashik Plant", 5, "Lakh Pieces"),
		],
		"turnovers": [("2024-2025", 1950, "50% Automotive, 50% Industrial"), ("2025-2026", 2100, "50% Automotive, 50% Industrial")],
		"machines": [
			{"machine_type": "Centerless Grinding", "maker": "Koyo, Micron", "quantity": 12},
			{"machine_type": "ID Bore Grinding", "maker": "Izumi, Lidkoping", "quantity": 22},
		],
		"technical": {
			"line": "Line 4 - Roller Face Grinding",
			"applications": ["ID Bore Grinding", "OD Grinding"],
			"volume": 19.7, "volume_unit": "Lakh Pieces", "segment_turnover": 1050,
			"competitors": ["Tyrolit", "GNO"],
			"wheels": [("89A400K3V111", "350x40x160", "50 M/s", "0.5 - 1 mm", 120), ("CX120K8V104B3", "34x3x6.5", "60 M/s", "-", 900)],
			"consumption": ("Abrasive Wheel", 2400),
			"manufacturing": ("Bearing Rings", "Heat Treatment", "In-House", "In-house hardening and tempering of rings"),
		},
		"visits": [
			{"days_ago": 20, "purpose": "Trial", "principal": "Noritake", "category": "Super Abrasive (Vitrified)", "status": "Prospect", "stage": "Trial / Sample",
			 "notes": "Trial of CBN wheel on Line 4 bore grinding. First 300 pcs OK.", "potential": "Wheel speed 60 M/s, 900 wheels/year potential", "competition": "Tyrolit running, price pressure",
			 "next_action": "Collect trial report", "next_in": 2, "expense": 650},
			{"days_ago": 3, "purpose": "Commercial", "principal": "Noritake", "category": "Super Abrasive (Vitrified)", "status": "Prospect", "stage": "Quotation Submitted",
			 "notes": "Submitted offer for bulk order after successful trial.", "next_action": "Follow up on PO", "next_in": 7, "expense": 650},
		],
	},
	{
		"name": "Godavari Roller Bearings Ltd.",
		"industry": "Bearing",
		"status": "Active Customer",
		"region": "West - MH",
		"turnover": 480,
		"group_turnover": 1080,
		"employees": 1200,
		"established": 1978,
		"segments": ["Bearings", "Balls & Rollers"],
		"principals": ["Noritake", "Everloy"],
		"contacts": [
			{"person_name": "Anil Joshi", "designation": "GM - Operations", "department": "Production", "phone": "+91 98230 22001", "email": "anil.joshi@godavaribearings.example", "is_primary": 1},
			{"person_name": "Priya Bhosale", "designation": "Quality Engineer", "department": "Quality", "phone": "+91 98230 22002"},
		],
		"plants": [
			{"plant_name": "Godavari Jalna Plant", "plant_location": "Jalna", "state": "Maharashtra", "pincode": "431203", "plant_address": "Additional MIDC, Jalna"},
		],
		"production": [
			("Cylindrical Rollers", "Godavari Jalna Plant", 25, "Lakh Pieces"),
			("Ball Bearings", "Godavari Jalna Plant", 1.75, "Lakh Pieces"),
		],
		"turnovers": [("2025-2026", 480, "Group turnover 1080 Cr")],
		"machines": [{"machine_type": "Centerless Grinding", "maker": "Cincinnati, Laven", "quantity": 8}],
		"technical": {
			"line": "Rocker Arm Bearing Line",
			"applications": ["Centerless Grinding"],
			"volume": 27, "volume_unit": "Lakh Pieces", "segment_turnover": 210,
			"competitors": ["Cumi"],
			"wheels": [("WA80K5V", "500x200x305", "45 M/s", "-", 60)],
			"consumption": ("Abrasive Wheel", 600),
			"manufacturing": ("Rollers", "Roller Grinding", "In-House", "Centerless grinding of rollers"),
		},
		"visits": [
			{"days_ago": 15, "purpose": "Routine", "principal": "Noritake", "category": "Grinding Stone (Vitrified)", "status": "Prospect", "stage": "Technical Discussion",
			 "notes": "Discussed conventional centerless wheels for Cincinnati machine.", "next_action": "Send offer for vitrified wheel", "next_in": 1, "expense": 1800},
			{"days_ago": 2, "purpose": "Trial", "principal": "Everloy", "category": "Carbide Products", "status": "Prospect", "stage": "Received Enquiry",
			 "notes": "Enquiry for carbide work-rest blades.", "next_action": "Share Everloy catalogue", "next_in": 4, "expense": 1800},
		],
	},
	{
		"name": "Kharagpur Bearing Works",
		"industry": "Bearing",
		"status": "Prospect",
		"region": "East - WB",
		"turnover": 250,
		"employees": 800,
		"established": 1992,
		"segments": ["Bearings"],
		"principals": ["Noritake"],
		"contacts": [
			{"person_name": "Subhash Ghosh", "designation": "Maintenance Manager", "department": "Production", "phone": "+91 94330 33001", "email": "subhash.ghosh@kbw.example", "is_primary": 1},
		],
		"plants": [
			{"plant_name": "KBW Kharagpur Plant", "plant_location": "Kharagpur", "state": "West Bengal", "pincode": "721301", "plant_address": "Industrial Estate, Kharagpur"},
		],
		"production": [
			("Ball Bearings", "KBW Kharagpur Plant", 22, "Lakh Pieces"),
			("Taper Roller Bearings", "KBW Kharagpur Plant", 3.25, "Lakh Pieces"),
		],
		"turnovers": [("2025-2026", 250, "")],
		"machines": [{"machine_type": "Track Grinding", "maker": "Toyo", "quantity": 6}],
		"technical": {
			"line": "TRB Lip & Track Line",
			"applications": ["Track Grinding"],
			"volume": 3.25, "volume_unit": "Lakh Pieces", "segment_turnover": 60,
			"competitors": ["Tyrolit"],
			"wheels": [("TA100J8V", "100x7.5x46", "50 M/s", "-", 300)],
			"consumption": ("Abrasive Wheel", 1200),
			"manufacturing": ("Bearing Rings", "Ring Turning", "Outsourced", "Turned rings bought from local vendors"),
		},
		"visits": [
			{"days_ago": 6, "purpose": "Routine", "principal": "Noritake", "category": "Super Abrasive (Vitrified)", "status": "Prospect", "stage": "Introduction",
			 "notes": "Introduction meeting, shared Noritake profile.", "next_action": "Get drawings for track wheel", "next_in": 5, "expense": 2400},
			{"days_ago": 1, "purpose": "Trial", "principal": "Noritake", "category": "Super Abrasive (Vitrified)", "status": "Prospect", "stage": "Trial / Sample",
			 "notes": "Trial wheels received for lip and track grinding.", "next_action": "Schedule trial", "next_in": 3, "expense": 900},
		],
	},
	{
		"name": "Kalinga Foils Pvt. Ltd.",
		"industry": "Foil",
		"status": "Prospect",
		"region": "East - OD",
		"turnover": 320,
		"employees": 450,
		"established": 2004,
		"segments": ["Foil"],
		"principals": ["Noritake"],
		"contacts": [
			{"person_name": "Manas Patnaik", "designation": "Roll Shop In-charge", "department": "Production", "phone": "+91 94370 44001", "email": "manas.patnaik@kalingafoils.example", "is_primary": 1},
		],
		"plants": [
			{"plant_name": "Kalinga Jharsuguda Plant", "plant_location": "Jharsuguda", "state": "Odisha", "pincode": "768201", "plant_address": "Lapanga Industrial Area, Jharsuguda"},
		],
		"production": [("Aluminium Foil", "Kalinga Jharsuguda Plant", 1500, "Tons")],
		"turnovers": [("2025-2026", 320, "")],
		"machines": [{"machine_type": "Roll Grinding", "maker": "Pomini", "quantity": 2}],
		"technical": {
			"line": "Foil Mill Roll Shop",
			"applications": ["Roll Grinding"],
			"volume": 1500, "volume_unit": "Tons", "segment_turnover": 320,
			"competitors": ["Tyrolit", "Asahi"],
			"wheels": [("GC220J5V", "600x75x305", "35 M/s", "-", 40)],
			"consumption": ("Abrasive Wheel", 40),
			"manufacturing": ("Foil", "Cold Rolling", "In-House", "Foil rolling mill with in-house roll shop"),
		},
		"visits": [
			{"days_ago": 12, "purpose": "Issue", "principal": "Noritake", "category": "Grinding Stone (Vitrified)", "status": "Prospect", "stage": "Technical Discussion",
			 "notes": "Required Ra 0.15 not achieved with present wheel.", "competition": "Tyrolit wheel on Pomini machine", "next_action": "Recommend 180 grit wheel", "next_in": 2, "expense": 3200},
			{"days_ago": 4, "purpose": "Commercial", "principal": "Noritake", "category": "Grinding Stone (Vitrified)", "status": "On Hold", "stage": "Quotation Submitted",
			 "notes": "Offer submitted; customer holding until new plant is ready.", "next_action": "Check plant readiness", "next_in": 30, "expense": 3200},
		],
	},
	{
		"name": "Saurashtra Balls & Rollers LLP",
		"industry": "Balls & Rollers",
		"status": "Active Customer",
		"region": "West - GUJ",
		"turnover": 250,
		"employees": 300,
		"established": 1998,
		"segments": ["Balls & Rollers"],
		"principals": ["Noritake"],
		"contacts": [
			{"person_name": "Hitesh Patel", "designation": "Proprietor", "department": "Purchase", "phone": "+91 98250 55001", "email": "hitesh.patel@saurashtraballs.example", "is_primary": 1},
			{"person_name": "Kiran Solanki", "designation": "Supervisor", "department": "Production", "phone": "+91 98250 55002"},
		],
		"plants": [
			{"plant_name": "Saurashtra Rajkot Plant", "plant_location": "Rajkot", "state": "Gujarat", "pincode": "360003", "plant_address": "Aji GIDC, Rajkot"},
		],
		"production": [("Steel Balls", "Saurashtra Rajkot Plant", 290, "Tons")],
		"turnovers": [("2024-2025", 230, "20% export"), ("2025-2026", 250, "20% export")],
		"machines": [{"machine_type": "Ball Lapping", "maker": "Local make", "quantity": 38}],
		"technical": {
			"line": "Ball Lapping Section",
			"applications": ["Ball Lapping"],
			"volume": 290, "volume_unit": "Tons", "segment_turnover": 250,
			"competitors": ["TVMK"],
			"wheels": [("L1 Lapping Plate", "610x100", "-", "-", 24)],
			"consumption": ("Honing Stone", 24),
			"manufacturing": ("Steel Balls", "Ball Lapping", "In-House", "Flashing, grinding and lapping in-house"),
		},
		"visits": [
			{"days_ago": 25, "purpose": "Commercial", "principal": "Noritake", "category": "Grinding Stone (Vitrified)", "status": "Won", "stage": "Order Received",
			 "notes": "Order received for L1 lapping plates.", "next_action": "Payment follow-up", "next_in": 10, "expense": 2600},
			{"days_ago": 5, "purpose": "Stock", "principal": "Noritake", "category": "Grinding Stone (Vitrified)", "status": "Prospect", "stage": "Received Enquiry",
			 "notes": "Checked stock; next quarter requirement 24 plates.", "next_action": "Send quotation for L1", "next_in": 6, "expense": 2600},
		],
	},
]
