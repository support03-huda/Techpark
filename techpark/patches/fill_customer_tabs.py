"""Fill the new Plants / Production / Commercial tables on every TP Customer
from the existing Plant, Customer Product Production and Customer Turnover records.

Only these tables: customer_sync.TABLES grew later (Contacts, Technical), and rebuilding
Contacts here would empty it before create_customer_contacts has migrated the rows."""

import frappe

from techpark.customer_sync import pull_from_records

TABLES = ["plants", "production", "turnovers"]


def execute():
	for customer in frappe.get_all("TP Customer", pluck="name"):
		pull_from_records(customer, TABLES)
