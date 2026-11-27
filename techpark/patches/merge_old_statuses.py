# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-27: live got all the master patches in one migrate: the masters patch made the new Regularise and also kept
# the old Regularization (still on 2 visits), so status_flow_regularise could not rename it. Merge the old name into
# the new one (visits and text copies follow); the same for Cancelled -> Lost.
import frappe

from techpark.masters import STATUS_TEXT_FIELDS, clear_keys

OLD = (("TP Sales Status", "Regularization", "Regularise"), ("TP Sales Status", "Cancelled", "Lost"))


def execute():
	for master, old, new in OLD:
		if not frappe.db.exists(master, old):
			continue
		frappe.rename_doc(master, old, new, merge=bool(frappe.db.exists(master, new)), force=True)
		if frappe.db.get_value(master, new, "option_name") != new:
			frappe.db.set_value(master, new, "option_name", new, update_modified=False)
		for doctype, field in STATUS_TEXT_FIELDS:
			if frappe.db.table_exists(doctype):
				frappe.db.sql(f"update `tab{doctype}` set `{field}` = %s where `{field}` = %s", (new, old))
	clear_keys()
