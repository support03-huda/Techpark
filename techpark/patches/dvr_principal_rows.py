"""Principal-wise DVR: every existing visit gets a principal row made from its single
Principal / Lead Stage / Lead Status, the old Lead Stage names become the new statuses (also on the
customers' Visits tab), and DVR Type / Department are filled in (Visit, Sales)."""

import frappe

from techpark.techpark.doctype.daily_visit_report.daily_visit_report import STAGE_PROGRESS, row_from_lead


def execute():
	frappe.db.sql("update `tabDaily Visit Report` set dvr_type = 'Visit' where ifnull(dvr_type, '') = ''")
	frappe.db.sql("update `tabDaily Visit Report` set department = 'Sales' where ifnull(department, '') = ''")

	with_rows = set(frappe.get_all("DVR Principal", filters={"parenttype": "Daily Visit Report"}, pluck="parent", distinct=True))
	visits = frappe.get_all(
		"Daily Visit Report",
		filters={"principal": ("is", "set")},
		fields=["name", "docstatus", "principal", "supplier_product_category", "lead_stage", "lead_status"],
	)
	for v in visits:
		if v.name in with_rows:
			continue
		row = row_from_lead(v.lead_stage, v.lead_status)
		status = row["sales_status"] or row["development_status"]
		child = frappe.get_doc(
			{
				"doctype": "DVR Principal",
				"parent": v.name,
				"parenttype": "Daily Visit Report",
				"parentfield": "principals",
				"idx": 1,
				"docstatus": v.docstatus,
				"principal": v.principal,
				"supplier_product_category": v.supplier_product_category,
				"progress": STAGE_PROGRESS.get(status, 0),
				**row,
			}
		)
		child.db_insert()
		frappe.db.set_value(
			"Daily Visit Report",
			v.name,
			{"lead_stage": status, "stage_completed": child.progress, "principal_list": v.principal},
			update_modified=False,
		)

	# The customers' Visits tab rows carry the same Lead Stage.
	for v in frappe.get_all("TP Customer Visit", filters={"record": ("is", "set")}, fields=["name", "record"]):
		stage, completed = frappe.db.get_value("Daily Visit Report", v.record, ["lead_stage", "stage_completed"]) or (None, 0)
		frappe.db.set_value("TP Customer Visit", v.name, {"lead_stage": stage, "stage_completed": completed}, update_modified=False)
