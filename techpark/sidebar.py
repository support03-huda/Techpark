# Copyright (c) 2026, Techpark International
"""Keep the TechPark desk menu in step with workspace_sidebar/techpark.json on every migrate.

Frappe 16.54 builds the desk menu from a "Sidebar" record (plus any "Custom Sidebar" saved from the
screen). It copied the TechPark Workspace Sidebar into a Sidebar once, when the site was upgraded, and
never again, so later menu changes (no Plants; Dashboard, Development Board, Opportunities, Tour Expense)
did not show. Older Frappe (the local bench, 16.33) has no Sidebar doctype and reads the Workspace
Sidebar, which migrate already imports from the file.
"""

import json

import frappe

SIDEBAR = "TechPark"
ITEM_FIELDS = (
	"label", "type", "link_type", "link_to", "icon", "child", "collapsible", "indent", "keep_closed", "show_arrow", "url",
)


def sync_sidebar():
	"""after_migrate: the TechPark Sidebar gets the items of the app's sidebar file; a menu customised
	from the screen for everyone (Custom Sidebar without a user) is dropped so the app's menu shows."""
	if not frappe.db.exists("DocType", "Sidebar"):
		return
	path = frappe.get_app_path("techpark", "workspace_sidebar", "techpark.json")
	with open(path) as f:
		items = json.load(f).get("items") or []

	item_meta = frappe.get_meta("Sidebar Item")
	rows = [
		{field: item.get(field) for field in ITEM_FIELDS if item_meta.has_field(field) and item.get(field) is not None}
		for item in items
	]
	if frappe.db.exists("Sidebar", SIDEBAR):
		sidebar = frappe.get_doc("Sidebar", SIDEBAR)
	else:
		sidebar = frappe.new_doc("Sidebar")
		sidebar.title = SIDEBAR
		sidebar.module = "TechPark"
		sidebar.header_icon = "small-file"
	sidebar.set("items", rows)
	sidebar.flags.ignore_permissions = True
	sidebar.flags.ignore_links = True
	sidebar.save()

	if frappe.db.exists("DocType", "Custom Sidebar"):
		for name in frappe.get_all("Custom Sidebar", filters={"module": "TechPark", "user": ("is", "not set")}, pluck="name"):
			frappe.delete_doc("Custom Sidebar", name, ignore_permissions=True, force=True)
	frappe.clear_cache()
