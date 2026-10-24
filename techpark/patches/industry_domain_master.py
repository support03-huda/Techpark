"""Industry on the Customer Master became a dropdown: create the standard industries
and one for every industry already typed on a customer, so existing values stay valid."""

import frappe

from techpark.install import seed_industries


def execute():
	frappe.db.sql("update `tabTP Customer` set industry_domain = trim(industry_domain) where industry_domain is not null")
	frappe.db.sql("update `tabTP Customer` set industry_domain = null where industry_domain = ''")
	existing = frappe.get_all("TP Customer", filters={"industry_domain": ("is", "set")}, pluck="industry_domain", distinct=True)
	seed_industries(existing)
