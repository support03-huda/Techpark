"""Fill the new Plants / Production / Commercial tables on every TP Customer
from the existing Plant, Customer Product Production and Customer Turnover records."""

import frappe

from techpark.customer_sync import pull_from_records


def execute():
	for customer in frappe.get_all("TP Customer", pluck="name"):
		pull_from_records(customer)
