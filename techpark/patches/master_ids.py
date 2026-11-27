# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-27 (client): every dropdown master value gets its ID (prefix + number, e.g. DVS-0001), in Sort Order
import frappe

from techpark.masters import ID_PREFIX, set_master_id


def execute():
	for master in ID_PREFIX:
		if not (frappe.db.table_exists(master) and frappe.db.has_column(master, "master_id")):
			continue
		# 2026-11-27: Sort Order where the master has one, else as made
		order_by = "sort_order asc, creation asc" if frappe.db.has_column(master, "sort_order") else "creation asc"
		for name in frappe.get_all(master, filters={"master_id": ("is", "not set")}, order_by=order_by, pluck="name"):
			doc = frappe.get_doc(master, name)
			set_master_id(doc)
			frappe.db.set_value(master, name, "master_id", doc.master_id, update_modified=False)
