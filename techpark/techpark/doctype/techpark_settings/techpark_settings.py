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
	"follow_up_escalation_days": 3,
	"prospect_cold_days": 30,
	"not_visited_days": 60,
	"lock_days": 15,
}
DAY_FIELDS = ("follow_up_escalation_days", "prospect_cold_days", "not_visited_days", "lock_days")


def fill_defaults():
	"""Write the default of every setting that was never saved (or a day limit saved as 0),
	so the form shows the values actually in use."""
	saved = dict(frappe.db.sql("select field, value from `tabSingles` where doctype = 'TechPark Settings'"))
	for field, value in DEFAULTS.items():
		if field not in saved or (field in DAY_FIELDS and cint(saved[field]) < 1):
			frappe.db.set_single_value("TechPark Settings", field, value)


class TechParkSettings(Document):
	def validate(self):
		for field in DAY_FIELDS:
			if cint(self.get(field)) >= 1:
				continue
			# Reminder limits are hidden while reminders are off: fill in the default, don't block saving.
			if field != "lock_days" and not cint(self.enable_reminders):
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
	return cint(value) if value not in (None, "") else DEFAULTS[field]
