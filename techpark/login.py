# Last edited: 2026-11-07
import frappe

# Desk users land on the TechPark Dashboard page after login (the old TechPark workspace was removed).
HOME = "/desk/techpark-dashboard"


def on_login(login_manager):
	"""Always land desk users on the TechPark Dashboard after login."""
	user = login_manager.user
	if frappe.db.get_value("User", user, "user_type") != "System User":
		return
	frappe.local.flags.home_page = HOME
