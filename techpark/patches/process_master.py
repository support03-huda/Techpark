# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Process became a master (client)
"""Create the Process master: the client's grinding processes and any value already used on an application."""

import frappe

PROCESSES = [
	"Internal Grinding",
	"Cylindrical Grinding",
	"Centerless Grinding",
	"Superfinishing",
	"Surface Grinding",
	"End-Face Grinding",
	"Double Disc Grinding (DDG)",
]


def execute():
	used = frappe.get_all("Customer Application", filters={"grinding_process": ("is", "set")}, pluck="grinding_process", distinct=True)
	for name in [*PROCESSES, *used]:
		name = (name or "").strip()
		if name and not frappe.db.exists("Process", name):
			frappe.get_doc({"doctype": "Process", "process_name": name}).insert(ignore_permissions=True)
