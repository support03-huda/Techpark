"""All TechPark reminders start switched off (TechPark Settings > Enable Reminders)."""

import frappe


def execute():
	frappe.db.set_single_value("TechPark Settings", "enable_reminders", 0)
