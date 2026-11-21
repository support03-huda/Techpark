# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Division / Process Stage moved from the Application master to the Technical Lead (client)
"""Technical Leads take the Division / Process Stage their Application had."""

import frappe


def execute():
	for doctype in ("TP Technical Lead", "TP Customer Technical Lead"):
		for field in ("division", "process_stage"):
			frappe.db.sql(
				f"""update `tab{doctype}` t join `tabCustomer Application` a on a.name = t.application_master
				set t.`{field}` = a.`{field}`
				where ifnull(t.`{field}`, '') = '' and ifnull(a.`{field}`, '') != ''"""
			)
