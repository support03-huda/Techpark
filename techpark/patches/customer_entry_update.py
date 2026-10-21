"""Customer entry spec update:

* create the Territory Region master (Region became a link) and fill each customer's Zone,
* standardise Financial Year on turnover records (2025-26 -> 2025-2026) and default
  Frequency to Annual, then refresh the customers' Commercial tab.
"""

import frappe

from techpark.customer_sync import pull_from_records
from techpark.install import seed_regions
from techpark.techpark.doctype.customer_turnover.customer_turnover import normalize_financial_year


def execute():
	seed_regions()

	for c in frappe.get_all("TP Customer", filters={"territory_region": ("is", "set")}, fields=["name", "territory_region"]):
		zone = frappe.db.get_value("Territory Region", c.territory_region, "zone")
		if zone:
			frappe.db.set_value("TP Customer", c.name, "zone", zone, update_modified=False)

	for doctype in ("Customer Turnover", "TP Customer Turnover"):
		frappe.db.set_value(doctype, {"frequency": ("is", "not set")}, "frequency", "Annual", update_modified=False)

	changed = set()
	for t in frappe.get_all("Customer Turnover", fields=["name", "customer", "financial_year"]):
		try:
			fy = normalize_financial_year(t.financial_year)
		except frappe.ValidationError:
			frappe.clear_messages()
			print(f"Turnover {t.name}: financial year {t.financial_year!r} left as is, fix it by hand")
			continue
		if fy != t.financial_year:
			frappe.db.set_value("Customer Turnover", t.name, "financial_year", fy, update_modified=False)
			changed.add(t.customer)

	for customer in changed:
		if frappe.db.exists("TP Customer", customer):
			pull_from_records(customer, ["turnovers"])
