# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: Technical Lead "Created On" for the leads made before the field existed
import frappe


def execute():
	frappe.db.sql("update `tabTP Technical Lead` set lead_created_on = creation where lead_created_on is null")
	frappe.db.sql(
		"""update `tabTP Customer Technical Lead` r join `tabTP Technical Lead` l on l.name = r.record
		set r.lead_created_on = l.lead_created_on where r.lead_created_on is null"""
	)
