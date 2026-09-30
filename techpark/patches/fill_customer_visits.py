"""Fill the Visits table on every TP Customer from its existing Daily Visit Reports.

fill_customer_tabs ran on some sites before the Visits table existed."""

import frappe

from techpark.customer_sync import pull_from_records


def execute():
	for customer in frappe.get_all("TP Customer", pluck="name"):
		pull_from_records(customer, ["visits"])
