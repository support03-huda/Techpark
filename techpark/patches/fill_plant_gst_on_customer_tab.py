"""Copy GSTIN / GST Registration Type from each Plant to its row on the customer's Plants tab, so
saving a customer (which pushes the tab rows to the Plant records) does not blank them."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabTP Customer Plant` row
		join `tabPlant` plant on plant.name = row.record
		set row.gstin = plant.gstin, row.gst_registration_type = plant.gst_registration_type
		where row.parenttype = 'TP Customer'
		"""
	)
