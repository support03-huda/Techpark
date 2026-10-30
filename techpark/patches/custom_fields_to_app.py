"""GSTIN / GST Registration Type (Plant) and Customer No. (TP Customer) were first added on the live
site as Custom Fields; they are standard fields of the app now. Remove the Custom Fields before the
model sync: deleting a Custom Field keeps its column, so the values stay and the standard field uses it."""

import frappe

CUSTOM_FIELDS = ("Plant-gstin", "Plant-gst_registration_type", "TP Customer-customer_no")


def execute():
	for name in CUSTOM_FIELDS:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True)
