# Last edited: 2026-11-27
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
	# 2026-11-27 (client): Trial Failed closes the lead (Evaluation Failed); Retest / Closed switched off
	("Trial Failed", 40, "Lost"),
	("Retest", 40, "Open"),
	("Closed", 40, "Lost"),
	("Successful Trial", 50, "Open"),
	# 2026-11-27 (client): two more steps, then Regularise moves the lead to Sales (Progress Regularised)
	("Bulk Trial Order", 55, "Open"),
	("Bulk Trial", 60, "Open"),
	("Regularise", 70, "Open"),
)
SALES = (
	# 2026-11-27 (client): Sales starts at Regularise (was Regularization, last); Bulk Trial PO moved to
	# Development (switched off here); Cancelled renamed Lost (closes the lead, Progress Lost)
	("Regularise", 70, "Open"),
	("Enquiry Follow-up", 75, "Open"),
	("Order Follow-up", 80, "Won"),
	("Delivery Follow-up", 85, "Won"),
	("Payment Follow-up", 90, "Won"),
	("On Hold", 50, "On Hold"),
	("Lost", 50, "Lost"),
	("Bulk Trial PO", 70, "Won"),
)
# 2026-11-27: switched off when made (still on old visits)
INACTIVE = {
	"TP Development Status": {"Retest", "Closed"},
	"TP Sales Status": {"Bulk Trial PO"},
	"TP Lead Progress": {"Not Started"},
}
# 2026-11-27 (client): the Lead Progress a visit's status sets on its Technical Lead (set on the status masters,
# these are the first values): every development step -> Under Development, Trial Failed -> Evaluation Failed
# (closes the lead), Regularise -> Regularised (moves it to Sales), Lost -> Lost (closes it)
STATUS_LEAD_PROGRESS = {
	"TP Development Status": {
		**{s: "Under Development" for s, _p, _r in DEVELOPMENT},
		"Trial Failed": "Evaluation Failed",
		"Closed": "Evaluation Failed",
		"Regularise": "Regularised",
	},
	"TP Sales Status": {"Lost": "Lost"},
}
DEFAULT_LEAD_PROGRESS = "To Start"  # 2026-11-27: first value; the master's "Default" tick decides
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
	"Bulk Trial Order": {"sets_bulk_trial_po": "Received"},  # 2026-11-27
	"Regularise": {"sets_regularised": "Regularised"},  # 2026-11-27: was Regularization
}
# 2026-11-26: what a Lead Progress does to the lead (set on the TP Lead Progress master; these are the first values)
LEAD_PROGRESS = {
	"Regularised": {"moves_to_stage": "Sales"},
	"Evaluation Failed": {"closes_lead": 1},
	"Lost": {"closes_lead": 1},  # 2026-11-27
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
	# 2026-11-27: To Start (default), Under Development and Lost added (client); Not Started switched off
	"TP Lead Progress": ("To Start", "Under Development", "Not Started", "Quoted", "Trial Order Received", "Under Trial", "Approved", "Regularised", "Evaluation Failed", "Lost"),
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

# 2026-11-27 (client): every master value has an ID (prefix + number, e.g. DVS-0001) next to its name; the name
# can be renamed (Frappe Rename) and the change reaches every record
ID_PREFIX = {
	"TP Stage": "STG",
	"TP Customer Type": "CTY",
	"TP Machine Maker": "MCM",
	"TP Distribution Channel": "DCH",
	"TP Lead Status": "LST",
	"TP Visit Type": "VTY",
	"TP Customer Status": "CST",
	"TP Frequency": "FRQ",
	"TP Process Type": "PRT",
	"TP Zone": "ZON",
	"TP Lead Progress": "LPG",
	"TP Priority": "PRI",
	"TP Sample Status": "SMP",
	"TP Trial Status": "TRS",
	"TP Bulk Trial PO Status": "BTP",
	"TP Regularised Status": "RGS",
	"TP Development Status": "DVS",
	"TP Sales Status": "SLS",
}
# 2026-11-27 (client: "apply it to all"): the app's other masters get an ID too (their name stays their title)
OTHER_ID_PREFIX = {
	"Principal": "PRN",
	"Territory Region": "TER",
	"Industry Domain": "IND",
	"Industry Segment": "ISG",
	"Process": "PRC",
	"Process stages": "PST",
	"TP Expense Type": "EXT",
	"Consumption Type": "CNT",
	"Customer Product": "CPR",
	"Department Type": "DPT",
	"Product Category": "PCT",
	"Product Segment": "PSG",
	"Supplier Product Category": "SPC",
	"TP Competitor": "CMP",
}
ID_PREFIX.update(OTHER_ID_PREFIX)

# 2026-11-27: where a status is kept as plain text (copied from the visits): a rename updates these too
STATUS_TEXT_FIELDS = (
	("TP Opportunity", "status"),
	("TP Opportunity Log", "status"),
	("TP Technical Lead", "current_status"),
	("TP Customer Technical Lead", "current_status"),
	("Daily Visit Report", "lead_stage"),
	("TP Customer Visit", "lead_stage"),
)
RENAME_TEXT = {"TP Development Status": STATUS_TEXT_FIELDS, "TP Sales Status": STATUS_TEXT_FIELDS}

CORE = {
	m: set(SEED[m])
	for m in (
		"TP Stage", "TP Lead Status", "TP Customer Status", "TP Development Status", "TP Sales Status", "TP Priority",
		# 2026-11-27: Samples / Trials / Bulk Trials PO / Regularised values can be renamed now (no logic uses their names)
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
			if master in CORE and frappe.db.has_column(master, "app_key") and frappe.db.exists(master, {"app_key": value}):
				continue  # 2026-11-27: renamed by the client (found by its App Key)
			doc = frappe.get_doc({"doctype": master, "option_name": value, "sort_order": (i + 1) * 10, "is_active": 1})
			if master in STATUS_MASTERS:
				doc.progress = extra["progress"].get(value, 0)
				doc.result = extra["result"].get(value, "Open")
				doc.update(MILESTONES.get(value, {}))
				doc.sets_lead_progress = STATUS_LEAD_PROGRESS.get(master, {}).get(value)  # 2026-11-27
			if master == "TP Lead Progress":
				doc.update(LEAD_PROGRESS.get(value, {}))
				doc.is_default = 1 if value == DEFAULT_LEAD_PROGRESS else 0  # 2026-11-27
			if value in INACTIVE.get(master, ()):
				doc.is_active = 0  # 2026-11-27
			if master in CORE and value in CORE[master]:
				doc.app_key = value  # 2026-11-27: the app finds it by this key
			if value in COLOURS.get(master, {}):
				doc.color = COLOURS[master][value]  # 2026-11-27
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
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)  # 2026-11-27: also when called with JSON filters
	extra = [[doctype, "is_active", "=", 1], [doctype, "name", "like", f"%{txt}%"]]
	if isinstance(filters, dict):
		filters = [[doctype, k, "=", v] if not isinstance(v, (list, tuple)) else [doctype, k, *v] for k, v in filters.items()]
	# 2026-11-27: all active values (a master is a short list): the dropdown's 10-result page cut off
	# the last ones (e.g. Successful Trial, 12th Development Status)
	# 2026-11-27: the ID is shown under the name (and can be searched)
	if frappe.db.has_column(doctype, "master_id"):
		extra = [[doctype, "is_active", "=", 1]]
		or_filters = [[doctype, "name", "like", f"%{txt}%"], [doctype, "master_id", "like", f"%{txt}%"]]
		fields = ["name", "master_id"]
	else:
		or_filters, fields = None, ["name"]
	return frappe.get_list(
		doctype, filters=[*(filters or []), *extra], or_filters=or_filters, fields=fields, order_by="sort_order asc, name asc",
		limit_page_length=0, as_list=True,
	)


def priority_order():
	"""2026-11-26: {High: 10, Medium: 20, Low: 30} from the TP Priority master (its Sort Order)."""
	if not frappe.db.table_exists("TP Priority"):
		return {v: i for i, v in enumerate(SEED["TP Priority"])}
	return {r.name: r.sort_order or 0 for r in frappe.get_all("TP Priority", fields=["name", "sort_order"])}


# 2026-11-27 (phase 2): colours shown on the boards / dashboard / lists (the master's Colour; these are the first values)
COLOURS = {
	"TP Stage": {"Development": "orange", "Sales": "blue", "Development + Sales": "yellow"},
	"TP Priority": {"High": "red", "Medium": "orange", "Low": "gray"},
	"TP Lead Progress": {
		"To Start": "gray", "Not Started": "gray", "Under Development": "blue", "Quoted": "orange", "Approved": "green",
		"Regularised": "green", "Evaluation Failed": "red", "Lost": "red",
	},
	"TP Customer Status": {"Active Customer": "green", "Prospect": "orange", "Under Development": "blue", "Inactive": "red"},
	"TP Sample Status": {"Received": "blue", "Supplied": "blue", "Received / Sent": "blue", "Can Use as Samples": "blue"},
	"TP Trial Status": {"To Try": "orange", "In Progress": "orange", "Successful": "green", "Failed": "red", "Not Tried": "gray"},
	"TP Bulk Trial PO Status": {"Received": "blue", "Successful": "green", "Failed": "red"},
	"TP Regularised Status": {"Regularised": "green", "Cost Problem": "red", "Not Regularised": "red"},
}

# 2026-11-27 (client, phase 2): the values the app's logic needs carry a fixed App Key (their first name); the code
# finds them by key, so every value can be renamed. K("TP Stage", "Sales") -> the current name of that stage.
KEYED = tuple(CORE)
STAGE, DEV_STATUS, SALES_STATUS = "TP Stage", "TP Development Status", "TP Sales Status"
CUSTOMER_STATUS, PRIORITY = "TP Customer Status", "TP Priority"


def _key_map():
	m = getattr(frappe.local, "tp_keys", None)
	if m is None:
		m = {}
		for master in KEYED:
			if frappe.db.table_exists(master) and frappe.db.has_column(master, "app_key"):
				m[master] = {
					r.app_key: r.name for r in frappe.get_all(master, filters={"app_key": ("is", "set")}, fields=["name", "app_key"])
				}
		frappe.local.tp_keys = m
	return m


def K(master, key):
	"""Current name of the value the app knows as `key` (the key itself before migrate)."""
	if not key:
		return key
	return _key_map().get(master, {}).get(key, key)


def key_of(master, name):
	"""App Key of a value (its name when it has none)."""
	return next((k for k, n in _key_map().get(master, {}).items() if n == name), name)


def keys_for_boot():
	return _key_map()


def colours():
	"""2026-11-27: {master: {value: colour}} from the masters' Colour."""
	out = {}
	for master in COLOURS:
		if frappe.db.table_exists(master) and frappe.db.has_column(master, "color"):
			out[master] = {r.name: r.color for r in frappe.get_all(master, filters={"color": ("is", "set")}, fields=["name", "color"])}
	return out


def clear_keys():
	frappe.local.tp_keys = None
	frappe.local.tp_status_rows = None


def set_master_id(doc):
	"""2026-11-27: the next ID of the master (e.g. DVS-0001; Frappe's series counter)."""
	from frappe.model.naming import make_autoname

	prefix = ID_PREFIX.get(doc.doctype)
	if prefix and not doc.get("master_id"):
		doc.master_id = make_autoname(f"{prefix}-.####", doc=doc)


def set_master_id_event(doc, method=None):
	"""2026-11-27: doc_events before_insert of the other masters (OTHER_ID_PREFIX)."""
	set_master_id(doc)


class DropdownMaster:
	"""Mixin of the master doctypes: the app's own values cannot be deleted or renamed."""

	def before_insert(self):
		set_master_id(self)  # 2026-11-27

	def after_rename(self, old, new, merge=False):
		"""2026-11-27: a renamed value: its Name field and the places that keep it as text follow."""
		if self.get("option_name") in (None, "", old):
			self.db_set("option_name", new, update_modified=False)
		for doctype, field in RENAME_TEXT.get(self.doctype, ()):
			if frappe.db.table_exists(doctype):
				frappe.db.sql(f"update `tab{doctype}` set `{field}` = %s where `{field}` = %s", (new, old))
		clear_keys()  # 2026-11-27

	def on_trash(self):
		# 2026-11-27: a value with an App Key is used by the app: switch it off instead (renaming is fine)
		if self.get("app_key"):
			frappe.throw(_("{0} is used by the app (cards, boards, stages): switch it off (Active) instead of deleting it.").format(frappe.bold(self.name)))
		clear_keys()

	def on_update(self):
		clear_keys()  # 2026-11-27
