# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""TechPark Settings — reminder limits and the edit lock for salespeople."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

DEFAULTS = {
	# Master switch for every reminder; off until turned on in TechPark Settings.
	"enable_reminders": 0,
	"reminder_emails": 1,
	# Pending Work reminders run on their own switch (on).
	"pending_work_reminders": 1,
	"follow_up_escalation_days": 3,
	"prospect_cold_days": 30,
	"not_visited_days": 60,
	"lock_days": 15,
	"stale_prospect_days": 7,  # 2026-11-26: dashboard (was hard coded)
	# 2026-11-26: General (were hard coded)
	"home_page": "/desk/techpark-dashboard",
	# 2026-11-26: name and address apart (a "Name <email>" text lost its <...> on save)
	"email_sender_name": "TechPark",
	"email_from": "support@softworld.co.in",
	"distributor_code": "TP",
	"financial_year_start": "4",
}
TEXT_FIELDS = ("home_page", "email_sender_name", "email_from", "distributor_code")  # 2026-11-26: not numbers
DAY_FIELDS = ("follow_up_escalation_days", "prospect_cold_days", "not_visited_days", "lock_days", "stale_prospect_days")
ALWAYS_ON = ("lock_days", "stale_prospect_days")  # 2026-11-26: not hidden with the reminders


def fill_defaults():
	"""Write the default of every setting that was never saved (or a day limit saved as 0),
	so the form shows the values actually in use."""
	saved = dict(frappe.db.sql("select field, value from `tabSingles` where doctype = 'TechPark Settings'"))
	for field, value in DEFAULTS.items():
		if field not in saved or (field in DAY_FIELDS and cint(saved[field]) < 1):
			frappe.db.set_single_value("TechPark Settings", field, value)


class TechParkSettings(Document):
	def on_update(self):
		from techpark.roles import clear_cache

		clear_cache()  # 2026-11-26: Roles
		# 2026-11-26: Company Logo / App Icon go to the login page, desk home icon and apps screen
		from techpark.branding import apply_branding

		apply_branding()

	def validate(self):
		for field in DAY_FIELDS:
			if cint(self.get(field)) >= 1:
				continue
			# Reminder limits are hidden while reminders are off: fill in the default, don't block saving.
			# 2026-11-26: an empty / 0 (never saved) limit also takes its default; only a negative one is refused
			if (field not in ALWAYS_ON and not cint(self.enable_reminders)) or self.get(field) in (None, "", 0):
				self.set(field, DEFAULTS[field])
			else:
				frappe.throw(_("{0} must be at least 1 day.").format(_(self.meta.get_label(field))))


def get_setting(field):
	"""Value from TechPark Settings, or the default when it was never saved."""
	# Read tabSingles directly: get_single_value() turns a never-saved Int into 0.
	row = frappe.db.sql(
		"select value from `tabSingles` where doctype = 'TechPark Settings' and field = %s", field
	)
	value = row[0][0] if row else None
	if value in (None, ""):
		return DEFAULTS[field]
	return value if field in TEXT_FIELDS else cint(value)  # 2026-11-26
