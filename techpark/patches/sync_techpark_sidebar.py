"""Frappe 16.54 skipped the updated TechPark sidebar on migrate, so it still showed Plants.
Load it from the app file again (one customer = one site: no Plants link)."""

import frappe
from frappe.modules.import_file import import_file_by_path


def execute():
	import_file_by_path(
		frappe.get_app_path("techpark", "workspace_sidebar", "techpark.json"), force=True, ignore_version=True
	)
	frappe.clear_cache()
