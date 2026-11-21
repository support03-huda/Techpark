# Copyright (c) 2026, Techpark International
"""Application "Process" is now a fixed list (the client's grinding processes). Old free text that is
one of them is kept; anything else moves into the Description. Technical Leads copy the master's Process."""

import frappe

PROCESSES = ["Internal Grinding", "Cylindrical Grinding", "Centerless Grinding", "Superfinishing", "Surface Grinding", "End-Face Grinding", "Double Disc Grinding (DDG)"]
ALIASES = {"ddg": "Double Disc Grinding (DDG)", "double disc grinding": "Double Disc Grinding (DDG)", "end face grinding": "End-Face Grinding", "centreless grinding": "Centerless Grinding", "super finishing": "Superfinishing"}


def execute():
	known = {p.lower(): p for p in PROCESSES}
	known.update(ALIASES)
	for app in frappe.get_all("Customer Application", fields=["name", "grinding_process", "description"]):
		text = (app.grinding_process or "").strip()
		if not text or text in PROCESSES:
			continue
		match = known.get(text.lower())
		if match:
			frappe.db.set_value("Customer Application", app.name, "grinding_process", match, update_modified=False)
			continue
		description = "\n".join(x for x in [(app.description or "").strip(), text] if x)
		frappe.db.set_value(
			"Customer Application", app.name, {"grinding_process": None, "description": description}, update_modified=False
		)

	for doctype in ("TP Technical Lead", "TP Customer Technical Lead"):
		frappe.db.sql(
			f"""update `tab{doctype}` t join `tabCustomer Application` a on a.name = t.application_master
			set t.grinding_process = a.grinding_process"""
		)
