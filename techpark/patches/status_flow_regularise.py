# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-27 (client): Development gets Bulk Trial Order, Bulk Trial, Regularise (Regularise -> lead to Sales,
# Progress Regularised); Trial Failed closes the lead (Progress Evaluation Failed); Retest / Closed switched off.
# Sales starts at Regularise (was Regularization), Bulk Trial PO switched off, Cancelled renamed Lost (lead closed,
# Progress Lost). Lead Progress: To Start (default), Under Development, Lost; each status says which Progress it sets.
import frappe

from techpark.masters import DEFAULT_LEAD_PROGRESS, INACTIVE, MILESTONES, STATUS_LEAD_PROGRESS, STATUS_MASTERS, seed

RENAMES = (("TP Sales Status", "Cancelled", "Lost"), ("TP Sales Status", "Regularization", "Regularise"))
# the visit statuses kept as plain text
TEXT_FIELDS = (
	("TP Opportunity", "status"),
	("TP Opportunity Log", "status"),
	("TP Technical Lead", "current_status"),
	("TP Customer Technical Lead", "current_status"),
	("Daily Visit Report", "lead_stage"),
	("TP Customer Visit", "lead_stage"),
)
CHANGED_RESULT = {"Trial Failed", "Closed", "Regularise", "Lost"}


def execute():
	for master, old, new in RENAMES:
		if frappe.db.exists(master, old) and not frappe.db.exists(master, new):
			frappe.rename_doc(master, old, new, force=True)
			frappe.db.set_value(master, new, "option_name", new, update_modified=False)
		for doctype, field in TEXT_FIELDS:
			if frappe.db.table_exists(doctype):
				frappe.db.sql(f"update `tab{doctype}` set `{field}` = %s where `{field}` = %s", (new, old))

	seed()  # new statuses and Lead Progress values

	for master, statuses in STATUS_MASTERS.items():
		for i, (status, progress, result) in enumerate(statuses):
			if not frappe.db.exists(master, status):
				continue
			values = {"sort_order": (i + 1) * 10}
			if status in CHANGED_RESULT:
				values.update(result=result, progress=progress)
			if status in INACTIVE.get(master, ()):
				values["is_active"] = 0
			if not frappe.db.get_value(master, status, "sets_lead_progress"):
				values["sets_lead_progress"] = STATUS_LEAD_PROGRESS.get(master, {}).get(status)
			for field, value in MILESTONES.get(status, {}).items():
				if not frappe.db.get_value(master, status, field):
					values[field] = value
			frappe.db.set_value(master, status, values, update_modified=False)

	for value in INACTIVE["TP Lead Progress"]:
		if frappe.db.exists("TP Lead Progress", value):
			frappe.db.set_value("TP Lead Progress", value, "is_active", 0, update_modified=False)
	if frappe.db.exists("TP Lead Progress", DEFAULT_LEAD_PROGRESS) and not frappe.db.exists("TP Lead Progress", {"is_default": 1}):
		frappe.db.set_value("TP Lead Progress", DEFAULT_LEAD_PROGRESS, "is_default", 1, update_modified=False)
	frappe.local.tp_status_rows = None

	fix_leads()


def fix_leads():
	"""Existing leads: no Progress / Not Started -> To Start, or what their current status sets now."""
	from techpark.opportunity import refresh_opportunity
	from techpark.statuses import default_lead_progress, progress_effect, status_lead_progress

	default = default_lead_progress()
	refresh = []
	for lead in frappe.get_all("TP Technical Lead", fields=["name", "progress", "stage", "current_status", "opportunity"]):
		target = None
		if lead.current_status:
			target = status_lead_progress("Sales" if lead.stage == "Sales" else "Development", lead.current_status)
			effect = progress_effect(target)
			# a manual Progress (Quoted, Under Trial ...) stays unless the status closes the lead or moves it
			if target and not (effect.closes_lead or effect.moves_to_stage) and lead.progress not in (None, "", "Not Started", default):
				target = None
		if not target and lead.progress in (None, "", "Not Started"):
			target = default
		if not target or target == lead.progress:
			continue
		frappe.db.set_value("TP Technical Lead", lead.name, "progress", target, update_modified=False)
		frappe.db.set_value("TP Customer Technical Lead", {"record": lead.name}, "progress", target, update_modified=False)
		if lead.opportunity:
			refresh.append(lead.opportunity)
	for name in dict.fromkeys(refresh):
		if frappe.db.exists("TP Opportunity", name):
			refresh_opportunity(name)
