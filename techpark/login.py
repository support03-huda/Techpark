import frappe
from frappe.utils.data import get_url_to_workspace

WORKSPACE = "TechPark"


def on_login(login_manager):
	"""Always land desk users on the TechPark workspace after login."""
	user = login_manager.user
	if frappe.db.get_value("User", user, "user_type") != "System User":
		return

	is_public = frappe.db.get_value("Workspace", WORKSPACE, "public")
	if is_public is None:
		return

	if frappe.db.get_value("User", user, "default_workspace") != WORKSPACE:
		frappe.db.set_value("User", user, "default_workspace", WORKSPACE)
		frappe.cache.hdel("home_page", user)
		frappe.cache.hdel("bootinfo", user)

	frappe.local.flags.home_page = get_url_to_workspace(WORKSPACE, is_public)
