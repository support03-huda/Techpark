# Copyright (c) 2026, Techpark International
"""Developments / opportunities from the visits.

Every principal row of a visit is one application line (customer + application / line + principal +
product category + wheel spec), the way the client follows a development: Introduction -> Enquiry ->
Sent to Principal -> Offer -> Trial PO -> Sample -> Trial -> Bulk Trial PO -> Regularised. A submitted
visit finds or makes the line's TP Opportunity and the opportunity takes its status, next action and
stage history from the line's latest submitted visit.
"""

import frappe
from frappe.utils import cstr, getdate


def sync_visit(dvr):
	"""DVR on_submit / on_update_after_submit: link every principal row to its opportunity and refresh it."""
	for row in dvr.principals:
		name = row.opportunity or find_or_make(dvr, row)
		if row.opportunity != name:
			row.db_set("opportunity", name, update_modified=False)
		refresh_opportunity(name)


def opportunity_key(customer, row):
	# As text: Product Categories are numbered (autoincrement) and the column holds text.
	return (customer, row.application, row.principal, cstr(row.supplier_product_category), cstr(row.spec))


def find_or_make(dvr, row):
	customer, application, principal, category, spec = opportunity_key(dvr.customer, row)
	found = frappe.db.sql(
		"""select name from `tabTP Opportunity`
		where customer = %s and application = %s and principal = %s
			and ifnull(supplier_product_category, '') = %s and ifnull(spec, '') = %s
		limit 1""",
		(customer, application, principal, category, spec),
	)
	if found:
		return found[0][0]
	doc = frappe.get_doc(
		{
			"doctype": "TP Opportunity",
			"customer": customer,
			"application": application,
			"principal": principal,
			"supplier_product_category": row.supplier_product_category,
			"spec": row.spec,
			"size": row.size,
			"sales_person": dvr.visited_by,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def refresh_opportunity(name):
	"""Status, next action, visit dates and stage history of an opportunity from its submitted visits."""
	from techpark.techpark.doctype.daily_visit_report.daily_visit_report import (
		LOST_STATUSES,
		STAGE_PROGRESS,
		WON_STATUSES,
	)

	if not frappe.db.exists("TP Opportunity", name):
		return
	rows = frappe.db.sql(
		"""
		select r.stage, r.development_status, r.sales_status, r.size, r.remark,
			r.next_action as row_next_action, r.next_action_date as row_next_action_date, r.follow_up as row_follow_up,
			d.name as dvr, d.visit_date, d.visited_by, d.next_action, d.next_action_date, d.follow_up
		from `tabDVR Principal` r
		join `tabDaily Visit Report` d on d.name = r.parent and r.parenttype = 'Daily Visit Report'
		where r.opportunity = %s and d.docstatus = 1
		order by d.visit_date, d.creation
		""",
		name,
		as_dict=True,
	)
	doc = frappe.get_doc("TP Opportunity", name)
	doc.set("history", [])
	last_status = None
	for r in rows:
		status = r.sales_status or r.development_status
		if status != last_status:
			doc.append(
				"history",
				{"date": r.visit_date, "status": status, "stage": r.stage, "visit": r.dvr, "by": r.visited_by, "remark": r.remark},
			)
			last_status = status

	latest = rows[-1] if rows else frappe._dict()
	status = latest.get("sales_status") or latest.get("development_status")
	doc.stage = latest.get("stage")
	doc.status = status
	doc.progress = STAGE_PROGRESS.get(status, 0)
	doc.lead_status = (
		"Won" if status in WON_STATUSES
		else "Lost" if status in LOST_STATUSES
		else "On Hold" if status == "On Hold"
		else "Open"
	)
	doc.next_action = latest.get("row_next_action") or latest.get("next_action")
	doc.next_action_date = latest.get("row_next_action_date") or latest.get("next_action_date")
	doc.follow_up = latest.get("row_follow_up") or latest.get("follow_up")
	doc.last_visit = latest.get("visit_date")
	doc.last_dvr = latest.get("dvr")
	doc.first_visit = rows[0].visit_date if rows else None
	doc.visits = len(rows)
	if latest.get("visited_by"):
		doc.sales_person = latest.visited_by
	if latest.get("size"):
		doc.size = latest.size
	set_milestones(doc, rows)
	doc.flags.ignore_permissions = True
	doc.save()


# Visit status -> value of the Samples / Trials / Bulk Trials PO / Regularised columns (the client's
# Development Status sheet). The latest matching visit wins.
MILESTONES = {
	"samples": {"Sample Received": "Received"},
	"trials": {
		"Trial PO Received": "To Try",
		"Sample Received": "To Try",
		"Trial in Progress": "In Progress",
		"Retest": "In Progress",
		"Successful Trial": "Successful",
		"Trial Failed": "Failed",
	},
	"bulk_trial_po": {"Bulk Trial PO": "Received"},
	"regularised": {"Regularization": "Regularised"},
}


def set_milestones(doc, rows):
	"""Fill the milestone columns from the visits. A value entered by hand that the visits cannot give
	(Supplied, Not Tried, Cost Problem ...) is kept, except that a regularisation always shows."""
	found = {}
	for r in rows:
		status = r.sales_status or r.development_status
		for field, mapping in MILESTONES.items():
			if status in mapping:
				found[field] = mapping[status]
		# In the Sales stage the trial was successful (also when a visit skipped the trial status).
		if r.stage == "Sales" and found.get("trials") != "Failed":
			found["trials"] = "Successful"
	for field, value in found.items():
		current = doc.get(field)
		if not current or current in MILESTONES[field].values() or value == "Regularised":
			doc.set(field, value)


def follow_up_state(opportunity, open_todos, today):
	"""Overdue / Due Soon / Planned while the follow-up is open; empty when done or none."""
	from frappe import _
	from frappe.utils import date_diff

	if not opportunity.next_action_date or (opportunity.follow_up and opportunity.follow_up not in open_todos):
		return ""
	days = date_diff(getdate(opportunity.next_action_date), today)
	if days < 0:
		return _("Overdue")
	return _("Due Soon") if days <= 3 else _("Planned")
