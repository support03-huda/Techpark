# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: TechPark Settings > Branding starts with the app's logo / icon (then changed from the screen)
import frappe

from techpark.branding import SHIPPED_ICON, SHIPPED_LOGO, apply_branding


def execute():
	for field, value in (("company_logo", SHIPPED_LOGO), ("app_icon", SHIPPED_ICON)):
		if not frappe.db.get_single_value("TechPark Settings", field):
			frappe.db.set_single_value("TechPark Settings", field, value)
	apply_branding()
