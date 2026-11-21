# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
"""DVR shows the Application's Process: fill it on existing visits."""

import frappe


def execute():
	frappe.db.sql(
		"""update `tabDaily Visit Report` d join `tabCustomer Application` a on a.name = d.application_master
		set d.grinding_process = a.grinding_process"""
	)
