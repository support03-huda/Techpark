# Copyright (c) 2026, Techpark International
"""DVR list shows the Product (principal product category name): fill it on existing visits."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabDaily Visit Report` d
		join `tabSupplier Product Category` c on c.name = d.supplier_product_category
		set d.product_name = c.category_name
		where ifnull(d.product_name, '') = ''
		"""
	)
