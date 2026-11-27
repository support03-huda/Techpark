# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""2026-11-26: which roles do what is set in TechPark Settings > Roles (client: nothing hard coded).
The DEFAULT_* values are only what a site starts with (patches/role_settings.py) and what is used
before that migrate ran."""

import frappe

DEFAULT_ROLES = {
	# see everything, approve, change locked entries
	"admin_roles": ("System Manager", "TechPark Approver"),
	# may open the TechPark app; their users are the salespeople of the dashboard
	"app_roles": ("Sales User", "Sales Manager"),
	# get the managers' reminder emails
	"reminder_roles": ("Sales Manager", "TechPark Approver"),
}
DEFAULT_APPROVER = "TechPark Approver"
# Choice in the registration approval dialog -> roles the new login gets
DEFAULT_REGISTRATION = (
	("Sales User", "Sales User"),
	("Sales Manager", "Sales User"),
	("Sales Manager", "Sales Manager"),
	("Admin", "Sales User"),
	("Admin", "Sales Manager"),
	("Admin", DEFAULT_APPROVER),
)


def _cache():
	if getattr(frappe.local, "tp_roles", None) is None:
		frappe.local.tp_roles = {}
	return frappe.local.tp_roles


def clear_cache():
	frappe.local.tp_roles = None


def _ready(field):
	return frappe.get_meta("TechPark Settings").has_field(field)


def _table(field):
	cache = _cache()
	if field not in cache:
		rows = []
		if _ready(field):
			child = frappe.get_meta("TechPark Settings").get_field(field).options
			rows = frappe.get_all(
				child, filters={"parent": "TechPark Settings", "parentfield": field}, fields=["*"], order_by="idx"
			)
		cache[field] = rows
	return cache[field]


def _roles(field):
	return {r.role for r in _table(field) if r.get("role")} or set(DEFAULT_ROLES[field])


def admin_roles():
	return _roles("admin_roles")


def app_roles():
	return _roles("app_roles")


def reminder_roles():
	return _roles("reminder_roles")


def approver_role():
	return (frappe.db.get_single_value("TechPark Settings", "approver_role") if _ready("approver_role") else None) or DEFAULT_APPROVER


def registration_choices():
	"""{choice: [roles]} in their order."""
	out = {}
	for r in _table("registration_roles"):
		if r.get("choice") and r.get("role"):
			out.setdefault(r.choice, []).append(r.role)
	if not out:
		for choice, role in DEFAULT_REGISTRATION:
			out.setdefault(choice, []).append(role)
	return out


def for_boot():
	"""What the desk scripts need (frappe.boot.techpark_roles)."""
	return {"admin": sorted(admin_roles()), "approver": approver_role()}
