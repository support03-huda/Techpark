"""Fill the new Technical tab tables (Segments, Wheel Specifications, Consumption,
Manufacturing) on every TP Customer from the existing records."""

import frappe

from techpark.customer_sync import pull_from_records

TECHNICAL_TABLES = ["segment_applications", "wheel_specs", "consumptions", "manufacturing_details"]


def execute():
	for customer in frappe.get_all("TP Customer", pluck="name"):
		pull_from_records(customer, TECHNICAL_TABLES)
