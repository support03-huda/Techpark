"""Repair `tabCompetitor` on sites where ERPNext took over the "Competitor" DocType name
from TechPark.

The table was created by TechPark with a numeric (autoincrement) name column; ERPNext names
competitors by their name, so every insert failed ("Incorrect integer value"). Any rows in it
were created by TechPark: move them to TP Competitor, then give the column ERPNext's type.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Competitor") or not frappe.db.table_exists("Competitor"):
		return
	if frappe.db.get_value("DocType", "Competitor", "module") == "TechPark":
		return
	if "int" not in (frappe.db.get_column_type("Competitor", "name") or "").lower():
		return  # already a text column, nothing to repair

	has_active = frappe.db.has_column("Competitor", "is_active")
	fields = "competitor_name, is_active" if has_active else "competitor_name"
	for row in frappe.db.sql(f"select {fields} from `tabCompetitor`", as_dict=True):
		name = (row.competitor_name or "").strip()
		if name and not frappe.db.exists("TP Competitor", {"competitor_name": name}):
			frappe.get_doc(
				{"doctype": "TP Competitor", "competitor_name": name, "is_active": row.get("is_active", 1)}
			).insert(ignore_permissions=True)

	frappe.db.delete("Competitor")
	frappe.db.change_column_type("Competitor", "name", f"varchar({frappe.db.VARCHAR_LEN})")
