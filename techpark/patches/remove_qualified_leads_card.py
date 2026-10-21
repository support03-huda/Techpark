"""The "Qualified Leads" number card counted Frappe CRM leads, which are not TechPark data.
It is replaced on the dashboard by "Overdue Follow-ups"; remove the old standard card."""

import frappe


def execute():
	if frappe.db.get_value("Number Card", "Qualified Leads", "module") == "TechPark":
		frappe.delete_doc("Number Card", "Qualified Leads", force=True, ignore_permissions=True)
