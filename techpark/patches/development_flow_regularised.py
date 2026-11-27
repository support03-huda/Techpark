# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: client flow: ... Trial Failed, Retest, Closed, Successful Trial in Development; Sales only once the
# lead's Progress is Regularised. Existing Sales-stage leads keep their stage (Progress = Regularised).
import frappe

from techpark.masters import DEVELOPMENT, seed


def execute():
	seed()
	for i, (status, _progress, result) in enumerate(DEVELOPMENT):
		if frappe.db.exists("TP Development Status", status):
			values = {"sort_order": (i + 1) * 10}
			if status in ("Trial Failed", "Closed"):
				values["result"] = result
			frappe.db.set_value("TP Development Status", status, values, update_modified=False)
	frappe.local.tp_status_rows = None

	regularised = frappe.db.get_value("TP Lead Progress", {"moves_to_stage": "Sales"})
	if regularised:
		for lead in frappe.get_all("TP Technical Lead", filters={"stage": "Sales", "is_closed": 0}, fields=["name", "progress"]):
			if lead.progress != regularised:
				frappe.db.set_value("TP Technical Lead", lead.name, "progress", regularised, update_modified=False)
				frappe.db.set_value("TP Customer Technical Lead", {"record": lead.name}, "progress", regularised, update_modified=False)

	from techpark.opportunity import refresh_opportunity

	# only the lines whose result changes (Trial Failed is open now; Lost lines close their lead)
	names = frappe.get_all("TP Opportunity", filters={"visits": (">", 0), "status": ("in", ("Trial Failed", "Closed"))}, pluck="name")
	names += frappe.get_all("TP Opportunity", filters={"visits": (">", 0), "lead_status": "Lost"}, pluck="name")
	for name in dict.fromkeys(names):
		refresh_opportunity(name)
