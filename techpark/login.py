# Last edited: 2026-11-26
import frappe

# Desk users land on TechPark Settings > Home Page After Login (2026-11-26; was hard coded to the dashboard).


def home():
	from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

	return get_setting("home_page")


def on_login(login_manager):
	"""Always land desk users on the TechPark Dashboard after login."""
	user = login_manager.user
	if frappe.db.get_value("User", user, "user_type") != "System User":
		return
	frappe.local.flags.home_page = home()
