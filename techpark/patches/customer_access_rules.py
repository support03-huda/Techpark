# Last edited: 2026-11-25
# Copyright (c) 2026, Techpark International
# 2026-11-25: client's first Customer Access rules (TechPark Settings > Customer Access)
"""Vedant and Shiv also see every Noritake / ALMT customer; Santosh also sees Vedant's and Shiv's customers.
Only users / principals that exist on the site are added, and only when the table is still empty."""

import frappe

VEDANT, SHIV, SANTOSH = "sales3@techpark.co.in", "sales2@techpark.co.in", "sales1@techpark.co.in"
RULES = [
	(VEDANT, "Noritake", None),
	(VEDANT, "ALMT", None),
	(SHIV, "Noritake", None),
	(SHIV, "ALMT", None),
	(SANTOSH, None, VEDANT),
	(SANTOSH, None, SHIV),
]


def execute():
	settings = frappe.get_single("TechPark Settings")
	if settings.get("customer_access"):
		return
	for user, principal, customers_of in RULES:
		if not frappe.db.exists("User", user) or (principal and not frappe.db.exists("Principal", principal)):
			continue
		if customers_of and not frappe.db.exists("User", customers_of):
			continue
		settings.append("customer_access", {"user": user, "principal": principal, "customers_of": customers_of})
	settings.flags.ignore_permissions = True
	settings.save()
