"""TechPark's "Competitor" DocType clashed with ERPNext's "Competitor" (DocType names are
global), so it is now "TP Competitor".

On sites where the TechPark DocType still owns the name, rename it in place so its records
and links are kept. Renaming moves the table but not the autoincrement sequence, so a new
sequence is started after the highest existing id.
"""

import frappe
from frappe.utils import cint


def execute():
	if frappe.db.exists("DocType", "TP Competitor"):
		return
	if frappe.db.get_value("DocType", "Competitor", "module") != "TechPark":
		return  # another app (ERPNext) owns "Competitor"; fix_competitor_table handles that case

	frappe.rename_doc("DocType", "Competitor", "TP Competitor", force=True)
	last = frappe.db.sql("select max(name) from `tabTP Competitor`")[0][0]
	frappe.db.create_sequence("TP Competitor", check_not_exists=True, start_value=cint(last) + 1)
