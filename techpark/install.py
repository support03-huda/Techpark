# Copyright (c) 2026, Techpark International
"""Default master data for a new site."""

import frappe

# Principals from the approved DVR spec. Categories are the Noritake product types
# used in the TECHPARK Negotiation List; add Everloy / ALMT categories from the desk.
PRINCIPALS = {
	"Noritake": ["Super Abrasive (Vitrified)", "Grinding Stone (Vitrified)", "Dresser"],
	"Everloy": [],
	"ALMT": [],
}

# Region -> zone. The zones themselves stay valid regions (customers created before
# regions became a master use them); the rest are the regions in the client's sales lists.
REGIONS = {
	"North": "North",
	"South": "South",
	"East": "East",
	"West": "West",
	"Central": "Central",
	"West - MH": "West",
	"West - GUJ": "West",
	"East - WB": "East",
	"East - JH": "East",
	"East - OD": "East",
}


def after_install():
	seed_principals()
	seed_regions()


def seed_regions():
	for region, zone in REGIONS.items():
		if not frappe.db.exists("Territory Region", region):
			frappe.get_doc({"doctype": "Territory Region", "region_name": region, "zone": zone}).insert(
				ignore_permissions=True
			)


def seed_principals():
	for principal, categories in PRINCIPALS.items():
		if not frappe.db.exists("Principal", principal):
			frappe.get_doc({"doctype": "Principal", "principal_name": principal}).insert(ignore_permissions=True)
		for category in categories:
			if not frappe.db.exists("Supplier Product Category", {"principal": principal, "category_name": category}):
				frappe.get_doc(
					{"doctype": "Supplier Product Category", "principal": principal, "category_name": category}
				).insert(ignore_permissions=True)
