# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""2026-11-26: Development / Sales Status from their masters (client: every dropdown is a master).
Progress % and what a status counts as (Won / Lost / On Hold) are read from TP Development Status /
TP Sales Status; until those exist (before migrate) the app's defaults in masters.py are used."""

import frappe

from techpark.masters import DEVELOPMENT, MILESTONES, SALES

# 2026-11-26: status master field -> Opportunity column it fills
MILESTONE_FIELDS = {
	"sets_samples": "samples",
	"sets_trials": "trials",
	"sets_bulk_trial_po": "bulk_trial_po",
	"sets_regularised": "regularised",
}

MASTERS = (("Development", "TP Development Status", DEVELOPMENT), ("Sales", "TP Sales Status", SALES))


def status_rows():
	"""[{name, stage, progress, result, is_active}] in Sort Order, Development first. Cached per request."""
	rows = getattr(frappe.local, "tp_status_rows", None)
	if rows is not None:
		return rows
	rows = []
	for stage, master, defaults in MASTERS:
		got = []
		if frappe.db.table_exists(master):
			fields = ["name", "progress", "result", "is_active"]
			fields += [f for f in MILESTONE_FIELDS if frappe.db.has_column(master, f)]  # 2026-11-26
			got = frappe.get_all(master, fields=fields, order_by="sort_order asc, creation asc")
		if not got:
			got = [frappe._dict(name=s, progress=p, result=r, is_active=1, **MILESTONES.get(s, {})) for s, p, r in defaults]
		rows += [frappe._dict(r, stage=stage, progress=int(r.progress or 0)) for r in got]
	frappe.local.tp_status_rows = rows
	return rows


def clear_cache(doc=None, method=None):
	frappe.local.tp_status_rows = None


def stage_progress():
	"""Status -> progress % (all statuses, also switched-off ones still on old visits)."""
	return {r.name: r.progress for r in status_rows()}


def stage_statuses(stage, active_only=True):
	"""Status -> progress % of one stage, in Sort Order (board columns)."""
	return {r.name: r.progress for r in status_rows() if r.stage == stage and (r.is_active or not active_only)}


def milestones():
	"""2026-11-26: {Opportunity column: {status: value}} from the status masters."""
	out = {col: {} for col in MILESTONE_FIELDS.values()}
	for r in status_rows():
		for field, col in MILESTONE_FIELDS.items():
			if r.get(field):
				out[col][r.name] = r.get(field)
	return out


def progress_effect(progress):
	"""2026-11-26: {moves_to_stage, closes_lead} of a TP Lead Progress."""
	if progress and frappe.db.has_column("TP Lead Progress", "moves_to_stage"):
		return frappe.db.get_value("TP Lead Progress", progress, ["moves_to_stage", "closes_lead"], as_dict=True) or frappe._dict()
	return frappe._dict()


def statuses_counting_as(result):
	return tuple(r.name for r in status_rows() if r.result == result)


@frappe.whitelist()
def get_status_progress():
	"""For the visit form's progress bar."""
	return stage_progress()
