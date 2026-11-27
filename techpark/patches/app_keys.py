# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-27 (client, phase 2): the master values the app's logic uses get their App Key (= their name now), so they
# can be renamed; the Colour of priorities / customer statuses / milestone values
import frappe

from techpark.masters import COLOURS, CORE, clear_keys


def execute():
	for master, values in CORE.items():
		if not frappe.db.has_column(master, "app_key"):
			continue
		for value in values:
			if frappe.db.exists(master, value) and not frappe.db.get_value(master, value, "app_key"):
				if not frappe.db.exists(master, {"app_key": value}):
					frappe.db.set_value(master, value, "app_key", value, update_modified=False)
	for master, colours in COLOURS.items():
		if not frappe.db.has_column(master, "color"):
			continue
		for value, colour in colours.items():
			if frappe.db.exists(master, value) and not frappe.db.get_value(master, value, "color"):
				frappe.db.set_value(master, value, "color", colour, update_modified=False)
	clear_keys()
