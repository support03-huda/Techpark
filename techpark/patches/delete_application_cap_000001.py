# Last edited: 2026-11-28
# Copyright (c) 2026, Techpark International
# 2026-11-28 (client asked to delete Customer Application CAP-000001 on live): its only link is a leftover row of the
# Wheel Specs table that was taken off TP Customer (customer 10209, hidden, cannot be edited from the screen or API).
# Blank that row's Application, then delete the application.
import frappe

APPLICATION = "CAP-000001"


def execute():
	if not frappe.db.exists("Customer Application", APPLICATION):
		return
	if frappe.db.table_exists("TP Customer Wheel Spec"):
		frappe.db.sql(
			"""update `tabTP Customer Wheel Spec` set application = null
			where application = %s and parenttype = 'TP Customer' and parentfield = 'wheel_specs'""",
			APPLICATION,
		)
	try:
		frappe.delete_doc("Customer Application", APPLICATION, ignore_permissions=True)
	except frappe.LinkExistsError:
		frappe.db.rollback()  # still used elsewhere on this site (e.g. dev): keep it, migrate goes on
