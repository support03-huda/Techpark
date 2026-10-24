"""Product ID starts at 201 (approved spec): renumber existing products 1, 2 … to 201, 202 …
(links on production records follow the rename) and let new products continue from there."""

import frappe

from techpark.install import PRODUCT_ID_START
from techpark.naming import start_autoincrement_at

OFFSET = PRODUCT_ID_START - 1


def execute():
	# Highest first, so a new number never collides with one still to be renamed.
	for name in frappe.get_all(
		"Customer Product", filters={"name": ("<", PRODUCT_ID_START)}, pluck="name", order_by="name desc"
	):
		new = int(name) + OFFSET
		if not frappe.db.exists("Customer Product", new):
			# Patches run as Administrator, so no permission override is needed.
			frappe.rename_doc("Customer Product", int(name), new, force=True, show_alert=False)

	start_autoincrement_at("Customer Product", PRODUCT_ID_START)
