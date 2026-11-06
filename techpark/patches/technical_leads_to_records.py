# Copyright (c) 2026, Techpark International
"""Technical Leads became their own records (TP Technical Lead): give every existing
customer-tab row its record so visits can pick it."""

import frappe

from techpark.customer_sync import TABLES


def execute():
	if not frappe.db.table_exists("TP Customer Technical Lead"):
		return
	cfg = TABLES["technical_leads"]
	rows = frappe.get_all(
		"TP Customer Technical Lead",
		filters={"parenttype": "TP Customer", "parentfield": "technical_leads"},
		fields=["name", "parent", "record", *cfg["fields"]],
	)
	for row in rows:
		if row.record and frappe.db.exists("TP Technical Lead", row.record):
			continue
		if not row.application:
			continue
		lead = frappe.get_doc(
			{"doctype": "TP Technical Lead", "customer": row.parent, **{f: row.get(f) for f in cfg["fields"]}}
		)
		lead.flags.ignore_links = True
		lead.flags.ignore_mandatory = True
		frappe.flags.tp_customer_sync = True  # the row already exists; don't rebuild the tab
		try:
			lead.insert(ignore_permissions=True)
		finally:
			frappe.flags.tp_customer_sync = False
		frappe.db.set_value("TP Customer Technical Lead", row.name, "record", lead.name, update_modified=False)
