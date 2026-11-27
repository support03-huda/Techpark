# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: Lead Progress decides the lead's stage / closing: fill the master, then the existing leads
import frappe

from techpark.masters import LEAD_PROGRESS, seed


def execute():
	seed()
	# Regularised was added after the others: keep the list in its seed order (Evaluation Failed last)
	from techpark.masters import SEED

	for i, progress in enumerate(SEED["TP Lead Progress"]):
		if frappe.db.exists("TP Lead Progress", progress):
			frappe.db.set_value("TP Lead Progress", progress, "sort_order", (i + 1) * 10, update_modified=False)
	for progress, values in LEAD_PROGRESS.items():
		if frappe.db.exists("TP Lead Progress", progress):
			frappe.db.set_value("TP Lead Progress", progress, values, update_modified=False)
	for lead in frappe.get_all("TP Technical Lead", filters={"progress": ("is", "set")}, pluck="name"):
		doc = frappe.get_doc("TP Technical Lead", lead)
		before = (doc.stage, doc.is_closed)
		doc.set_progress_effect()
		if (doc.stage, doc.is_closed) != before:
			doc.db_set({"stage": doc.stage, "is_closed": doc.is_closed}, update_modified=False)
			if doc.opportunity:
				from techpark.opportunity import refresh_opportunity

				refresh_opportunity(doc.opportunity)
