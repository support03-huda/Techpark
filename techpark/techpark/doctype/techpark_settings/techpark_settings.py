# Copyright (c) 2026, Techpark International
"""TechPark Settings — reminder limits and the edit lock for salespeople."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

DEFAULTS = {
	"reminder_emails": 1,
	"follow_up_escalation_days": 3,
	"prospect_cold_days": 30,
	"not_visited_days": 60,
	"lock_days": 15,
}


class TechParkSettings(Document):
	def validate(self):
		for field in DEFAULTS:
			if field != "reminder_emails" and cint(self.get(field)) < 1:
				frappe.throw(_("{0} must be at least 1 day.").format(_(self.meta.get_label(field))))


def get_setting(field):
	"""Value from TechPark Settings, or the default when it was never saved."""
	# Read tabSingles directly: get_single_value() turns a never-saved Int into 0.
	row = frappe.db.sql(
		"select value from `tabSingles` where doctype = 'TechPark Settings' and field = %s", field
	)
	value = row[0][0] if row else None
	return cint(value) if value not in (None, "") else DEFAULTS[field]
