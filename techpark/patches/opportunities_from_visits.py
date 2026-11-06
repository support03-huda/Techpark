"""The client's development cycle (2026-11-06): move visits to the new statuses, give every principal row
an application line and build the TP Opportunity of each line from the submitted visits."""

import frappe

from techpark.opportunity import sync_visit
from techpark.techpark.doctype.daily_visit_report.daily_visit_report import GENERAL_APPLICATION, STAGE_PROGRESS

DEVELOPMENT = {"Requirement Shared": "Enquiry Received", "Sample / Trial Planned": "Trial PO Received"}
# Quotation / negotiation after the trial is no longer a status: the row stays at the successful trial.
SALES = {"Quotation Submitted": None, "Negotiation": None, "Order Won": "Bulk Trial PO", "Order Lost": "Cancelled"}
LEAD_STAGE = {
	**DEVELOPMENT,
	"Quotation Submitted": "Offer Submitted",
	"Negotiation": "Offer Submitted",
	"Order Won": "Bulk Trial PO",
	"Order Lost": "Cancelled",
}


def execute():
	for old, new in DEVELOPMENT.items():
		frappe.db.sql("update `tabDVR Principal` set development_status = %s where development_status = %s", (new, old))
	for old, new in SALES.items():
		frappe.db.sql("update `tabDVR Principal` set sales_status = %s where sales_status = %s", (new, old))
	for doctype in ("Daily Visit Report", "TP Customer Visit"):
		for old, new in LEAD_STAGE.items():
			frappe.db.sql(f"update `tab{doctype}` set lead_stage = %s where lead_stage = %s", (new, old))

	# Application line: the visit's Segment / Line, else General.
	frappe.db.sql(
		"""update `tabDVR Principal` r
		join `tabDaily Visit Report` d on d.name = r.parent and r.parenttype = 'Daily Visit Report'
		left join `tabCustomer Segment Application` s on s.name = d.segment_application
		set r.application = coalesce(nullif(s.sub_category_line, ''), %s)
		where ifnull(r.application, '') = ''""",
		GENERAL_APPLICATION,
	)
	for status, progress in STAGE_PROGRESS.items():
		frappe.db.sql(
			"""update `tabDVR Principal` set progress = %s
			where ifnull(nullif(sales_status, ''), development_status) = %s""",
			(progress, status),
		)

	for name in frappe.get_all("Daily Visit Report", filters={"docstatus": 1}, pluck="name", order_by="visit_date, creation"):
		sync_visit(frappe.get_doc("Daily Visit Report", name))
