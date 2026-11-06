"""TP Quotation and TP Sales Follow-up were dropped (2026-11-06): the sales follow-up stays in the
visit's Sales stage with its next-action reminders. Remove them from sites that already had them."""

import frappe


def execute():
	for doctype in ("TP Sales Follow-up", "TP Quotation"):
		if frappe.db.exists("DocType", doctype):
			frappe.db.delete("ToDo", {"reference_type": doctype})
			frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
