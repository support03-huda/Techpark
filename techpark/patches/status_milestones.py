# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: which Opportunity column each status fills is now on the status masters (was in opportunity.py)
import frappe

from techpark.masters import MILESTONES, seed


def execute():
	seed()
	for master in ("TP Development Status", "TP Sales Status"):
		for status, values in MILESTONES.items():
			if frappe.db.exists(master, status):
				for field, value in values.items():
					if not frappe.db.get_value(master, status, field):
						frappe.db.set_value(master, status, field, value, update_modified=False)
