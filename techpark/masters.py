# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
"""2026-11-26: every dropdown is a master (client): the fixed Select lists became small doctypes the client
can add to, order (Sort Order), switch off (Active) and, for the Development / Sales Status, give a
Progress % and what it counts as (Open / Won / Lost / On Hold).

SEED: the values the lists had; seed() makes them (and any other value already saved) on migrate / install.
CORE: values the app's code relies on (cards, boards, stage logic): they cannot be deleted or renamed.
"""

import frappe
from frappe import _

DEVELOPMENT = (
	("Introduction", 5, "Open"),
	("Enquiry Received", 10, "Open"),
	("Sent to Principal", 15, "Open"),
	("Offer Received", 20, "Open"),
	("Offer Submitted", 25, "Open"),
	("Trial PO Received", 30, "Open"),
	("Sample Received", 35, "Open"),
	("Trial in Progress", 40, "Open"),
	# 2026-11-26: client order: Trial Failed (9), Retest, Closed, Successful Trial. A failed trial can be retested
	# (Open); Closed ends the line (off the boards, lead closed).
	("Trial Failed", 40, "Open"),
	("Retest", 40, "Open"),
	("Closed", 40, "Lost"),
	("Successful Trial", 50, "Open"),
)
SALES = (
	("Bulk Trial PO", 70, "Won"),
	("Enquiry Follow-up", 75, "Open"),
	("Order Follow-up", 80, "Won"),
	("Delivery Follow-up", 85, "Won"),
	("Payment Follow-up", 90, "Won"),
	("Regularization", 100, "Won"),
	("On Hold", 50, "On Hold"),
	("Cancelled", 50, "Lost"),
)
# 2026-11-26: status -> the Opportunity column it fills (Samples / Trials / Bulk Trials PO / Regularised); set on the
# status masters, these are their first values
MILESTONES = {
	"Sample Received": {"sets_samples": "Received", "sets_trials": "To Try"},
	"Trial PO Received": {"sets_trials": "To Try"},
	"Trial in Progress": {"sets_trials": "In Progress"},
	"Retest": {"sets_trials": "In Progress"},
	"Successful Trial": {"sets_trials": "Successful"},
	"Trial Failed": {"sets_trials": "Failed"},
	"Bulk Trial PO": {"sets_bulk_trial_po": "Received"},
	"Regularization": {"sets_regularised": "Regularised"},
}
# 2026-11-26: what a Lead Progress does to the lead (set on the TP Lead Progress master; these are the first values)
LEAD_PROGRESS = {
	"Regularised": {"moves_to_stage": "Sales"},
	"Evaluation Failed": {"closes_lead": 1},
}
STATUS_MASTERS = {"TP Development Status": DEVELOPMENT, "TP Sales Status": SALES}

SEED = {
	"TP Stage": ("Development", "Sales", "Development + Sales"),
	"TP Customer Type": ("Company", "Individual"),
	"TP Machine Maker": (),  # 2026-11-26: the makers already typed on the leads are made on migrate  # 2026-11-26: the last Select lists (client: nothing hard coded)
	"TP Distribution Channel": ("Direct (Commission)", "Indirect Business"),
	"TP Lead Status": ("Prospect", "Won", "Lost", "On Hold"),  # 2026-11-26: Stage is a master too (client)
	"TP Visit Type": ("Visit", "Phone Call", "Email", "Video Call", "WhatsApp", "Meeting"),
	"TP Customer Status": ("Prospect", "Under Development", "Active Customer", "Inactive"),
	"TP Frequency": ("Daily", "Weekly", "Monthly", "Quarterly", "Half-Yearly", "Annual", "Yearly"),
	"TP Process Type": ("In-House", "Outsourced", "Hybrid"),
	"TP Zone": ("North", "South", "East", "West", "Central"),
	"TP Lead Progress": ("Not Started", "Quoted", "Trial Order Received", "Under Trial", "Approved", "Regularised", "Evaluation Failed"),
	"TP Priority": ("High", "Medium", "Low"),
	"TP Sample Status": ("Received", "Supplied", "Received / Sent", "Can Use as Samples"),
	"TP Trial Status": ("To Try", "In Progress", "Successful", "Failed", "Not Tried"),
	"TP Bulk Trial PO Status": ("Received", "Successful", "Failed"),
	"TP Regularised Status": ("Regularised", "Cost Problem", "Not Regularised"),
	"TP Development Status": tuple(s for s, _p, _r in DEVELOPMENT),
	"TP Sales Status": tuple(s for s, _p, _r in SALES),
}

# Master -> label of its name field
LABELS = {
	"TP Stage": "Stage",
	"TP Customer Type": "Customer Type",
	"TP Machine Maker": "Machine Maker",
	"TP Distribution Channel": "Distribution Channel",
	"TP Lead Status": "Lead Status",
	"TP Visit Type": "Visit Type",
	"TP Customer Status": "Customer Status",
	"TP Frequency": "Frequency",
	"TP Process Type": "Process Type",
	"TP Zone": "Zone",
	"TP Lead Progress": "Progress",
	"TP Priority": "Priority",
	"TP Sample Status": "Samples",
	"TP Trial Status": "Trials",
	"TP Bulk Trial PO Status": "Bulk Trials PO",
	"TP Regularised Status": "Regularised",
	"TP Development Status": "Development Status",
	"TP Sales Status": "Sales Status",
}

# (doctype, field) -> master: the fields that were Select lists
FIELDS = (
	("Daily Visit Report", "dvr_stage", "TP Stage"),
	("TP Customer", "customer_type", "TP Customer Type"),
	# 2026-11-26: Technical Lead (and where its stage is copied)
	("TP Technical Lead", "stage", "TP Stage"),
	("TP Customer Technical Lead", "stage", "TP Stage"),
	("DVR Principal", "stage", "TP Stage"),
	("TP Opportunity", "stage", "TP Stage"),
	("TP Opportunity Log", "stage", "TP Stage"),
	("TP Technical Lead", "machine_maker", "TP Machine Maker"),
	("TP Customer Technical Lead", "machine_maker", "TP Machine Maker"),
	("TP Technical Lead", "distribution_channel", "TP Distribution Channel"),
	("TP Customer Technical Lead", "distribution_channel", "TP Distribution Channel"),
	("TP Customer Visit", "lead_status", "TP Lead Status"),
	("Daily Visit Report", "dvr_type", "TP Visit Type"),
	("TP Customer Visit", "dvr_type", "TP Visit Type"),
	("Daily Visit Report", "development_status", "TP Development Status"),
	("DVR Principal", "development_status", "TP Development Status"),
	("Daily Visit Report", "sales_status", "TP Sales Status"),
	("DVR Principal", "sales_status", "TP Sales Status"),
	("TP Customer", "customer_status", "TP Customer Status"),
	("Customer Product Production", "frequency", "TP Frequency"),
	("Customer Turnover", "frequency", "TP Frequency"),
	("TP Customer Consumption", "frequency", "TP Frequency"),
	("TP Customer Production", "frequency", "TP Frequency"),
	("TP Customer Turnover", "frequency", "TP Frequency"),
	("Wheel Consumption", "frequency", "TP Frequency"),
	("Manufacturing Details", "process_type", "TP Process Type"),
	("TP Customer Manufacturing", "process_type", "TP Process Type"),
	("Territory Region", "zone", "TP Zone"),
	("TP Technical Lead", "progress", "TP Lead Progress"),
	("TP Customer Technical Lead", "progress", "TP Lead Progress"),
	("TP Opportunity", "importance", "TP Priority"),
	("TP Pending Work", "priority", "TP Priority"),
	("TP Opportunity", "samples", "TP Sample Status"),
	("TP Opportunity", "trials", "TP Trial Status"),
	("TP Opportunity", "bulk_trial_po", "TP Bulk Trial PO Status"),
	("TP Opportunity", "regularised", "TP Regularised Status"),
)
# Computed from the statuses (any Development / Sales Status, also new ones): plain text now
TEXT_FIELDS = (
	("Daily Visit Report", "lead_stage"),
	("TP Opportunity", "status"),
	("TP Customer Visit", "lead_stage"),
)

CORE = {
	m: set(SEED[m])
	for m in (
		"TP Stage", "TP Lead Status", "TP Customer Status", "TP Development Status", "TP Sales Status", "TP Priority",
		"TP Sample Status", "TP Trial Status", "TP Bulk Trial PO Status", "TP Regularised Status",
	)
}


def seed():
	"""Make the seed values and every value already saved in the mapped fields (patch + after_install)."""
	for master, values in SEED.items():
		if not frappe.db.table_exists(master):
			continue
		extra = {
			"progress": {s: p for s, p, _r in STATUS_MASTERS.get(master, ())},
			"result": {s: r for s, _p, r in STATUS_MASTERS.get(master, ())},
		}
		saved = []
		for doctype, field, m in FIELDS:
			if m == master and frappe.db.table_exists(doctype):
				# 2026-11-26: typed values: no spaces around (they become master names)
				frappe.db.sql(f"update `tab{doctype}` set `{field}` = trim(`{field}`) where `{field}` != trim(`{field}`)")
				saved += [
					v.strip() for v in frappe.db.sql_list(f"select distinct `{field}` from `tab{doctype}` where ifnull(`{field}`, '') != ''")
				]
		for i, value in enumerate(dict.fromkeys([*values, *saved])):
			if frappe.db.exists(master, value):
				continue
			doc = frappe.get_doc({"doctype": master, "option_name": value, "sort_order": (i + 1) * 10, "is_active": 1})
			if master in STATUS_MASTERS:
				doc.progress = extra["progress"].get(value, 0)
				doc.result = extra["result"].get(value, "Open")
				doc.update(MILESTONES.get(value, {}))
			if master == "TP Lead Progress":
				doc.update(LEAD_PROGRESS.get(value, {}))
			if master == "TP Stage" and value == "Development + Sales":
				doc.is_active = 0  # 2026-11-26: only on old visits, not offered
			doc.flags.ignore_permissions = True
			doc.insert()
	frappe.db.commit()  # 2026-11-26: also runs after every migrate (hooks.py)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def master_query(doctype, txt, searchfield, start, page_len, filters):
	"""2026-11-26: every master dropdown: active values in their Sort Order (not A-Z)."""
	if doctype not in SEED:
		frappe.throw(_("Not a dropdown master: {0}").format(doctype))
	extra = [[doctype, "is_active", "=", 1], [doctype, "name", "like", f"%{txt}%"]]
	if isinstance(filters, dict):
		filters = [[doctype, k, "=", v] if not isinstance(v, (list, tuple)) else [doctype, k, *v] for k, v in filters.items()]
	return frappe.get_list(
		doctype, filters=[*(filters or []), *extra], fields=["name"], order_by="sort_order asc, name asc",
		limit_start=start, limit_page_length=page_len, as_list=True,
	)


def priority_order():
	"""2026-11-26: {High: 10, Medium: 20, Low: 30} from the TP Priority master (its Sort Order)."""
	if not frappe.db.table_exists("TP Priority"):
		return {v: i for i, v in enumerate(SEED["TP Priority"])}
	return {r.name: r.sort_order or 0 for r in frappe.get_all("TP Priority", fields=["name", "sort_order"])}


class DropdownMaster:
	"""Mixin of the master doctypes: the app's own values cannot be deleted or renamed."""

	def on_trash(self):
		if self.name in CORE.get(self.doctype, ()):
			frappe.throw(_("{0} is used by the app (cards, boards, stages): switch it off (Active) instead of deleting it.").format(frappe.bold(self.name)))

	def before_rename(self, old, new, merge=False):
		if old in CORE.get(self.doctype, ()):
			frappe.throw(_("{0} is used by the app (cards, boards, stages) and cannot be renamed.").format(frappe.bold(old)))
