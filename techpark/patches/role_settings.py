# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: TechPark Settings > General / Roles start with the values that were in the code
import frappe

from techpark.roles import DEFAULT_APPROVER, DEFAULT_REGISTRATION, DEFAULT_ROLES
from techpark.techpark.doctype.techpark_settings.techpark_settings import DEFAULTS


def execute():
	from techpark.techpark.doctype.techpark_settings.techpark_settings import fill_defaults

	fill_defaults()  # values never saved since their field was added (e.g. Prospect Stale After)
	settings = frappe.get_single("TechPark Settings")
	for field in ("home_page", "email_sender_name", "email_from", "distributor_code", "financial_year_start"):
		# 2026-11-26: email_from saved as "TechPark " (no address) is fixed too
		if not settings.get(field) or (field == "email_from" and "@" not in settings.get(field)):
			settings.set(field, DEFAULTS[field])
	if not settings.approver_role:
		settings.approver_role = DEFAULT_APPROVER
	for field, roles in DEFAULT_ROLES.items():
		if not settings.get(field):
			for role in roles:
				if frappe.db.exists("Role", role):
					settings.append(field, {"role": role})
	if not settings.get("registration_roles"):
		for choice, role in DEFAULT_REGISTRATION:
			if frappe.db.exists("Role", role):
				settings.append("registration_roles", {"choice": choice, "role": role})
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)
