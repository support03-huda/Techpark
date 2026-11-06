# Copyright (c) 2026, Techpark International
"""Current Wheel Usage is back on the customer (Products Info): rebuild its rows from the
Wheel Specification records."""

import frappe

from techpark.customer_sync import pull_from_records


def execute():
	for customer in frappe.get_all("Wheel Specification", pluck="customer", distinct=True):
		if customer and frappe.db.exists("TP Customer", customer):
			pull_from_records(customer, ["wheel_specs"])
