# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Technical Lead shows Principal Product Spec / Size from its DVRs (client)
"""Existing leads take Spec / Size from their latest submitted DVR (only where still empty)."""

import frappe


def execute():
	visits = frappe.get_all(
		"Daily Visit Report",
		filters={"docstatus": 1, "technical_lead": ("is", "set")},
		fields=["technical_lead", "spec", "size"],
		order_by="visit_date desc, creation desc",
	)
	done = set()
	for v in visits:
		if v.technical_lead in done or not (v.spec or v.size):
			continue
		done.add(v.technical_lead)
		lead = frappe.db.get_value("TP Technical Lead", v.technical_lead, ["spec", "size"], as_dict=True)
		if not lead:
			continue
		values = {f: v[f] for f in ("spec", "size") if v[f] and not lead[f]}
		if values:
			frappe.db.set_value("TP Technical Lead", v.technical_lead, values, update_modified=False)
			frappe.db.set_value("TP Customer Technical Lead", {"record": v.technical_lead}, values, update_modified=False)
