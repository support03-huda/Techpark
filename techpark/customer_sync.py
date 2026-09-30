# Copyright (c) 2026, Techpark International
"""Two-way sync between the TP Customer tabs and the real records.

The Plants / Production / Commercial / Visits tabs on TP Customer are editable
child tables. The real Plant, Customer Product Production, Customer Turnover
and Daily Visit Report records stay the source of truth (reports, links and
notifications use them):

* Saving a TP Customer pushes its rows to the records: new row -> new record,
  edited row -> record updated, removed row -> record deleted.
* Saving or deleting a record anywhere else rebuilds that customer's table
  (doc_events in hooks.py), so the tab never goes stale.

Each child row keeps the id of its record in `record`.

Visits are submittable: a new or draft row is submitted on save when
"Submit DVR on Save" is ticked; on submitted visits only Lead Status / Lead Stage
can be changed (Allow on Submit); anything else is amended or cancelled from the DVR itself.
"""

import frappe
from frappe import _
from frappe.utils import cstr, flt, now_datetime

# Order matters: plants first, the other tables may point to them.
TABLES = {
	"plants": {
		"label": "Plants",
		"child": "TP Customer Plant",
		"doctype": "Plant",
		"fields": ["plant_name", "plant_location", "state", "pincode", "is_active", "country", "plant_address"],
	},
	"production": {
		"label": "Production",
		"child": "TP Customer Production",
		"doctype": "Customer Product Production",
		"fields": ["plant", "product", "production_volume", "unit", "frequency", "department", "remarks"],
	},
	"turnovers": {
		"label": "Commercial",
		"child": "TP Customer Turnover",
		"doctype": "Customer Turnover",
		"fields": ["financial_year", "plant", "amount", "unit", "remarks"],
	},
	"visits": {
		"label": "Visits",
		"child": "TP Customer Visit",
		"doctype": "Daily Visit Report",
		"fields": [
			"visit_date",
			"plant",
			"visit_purpose",
			"contact_person",
			"lead_status",
			"lead_stage",
			"visited_by",
			"discussion_notes",
			"customer_requirement",
			"next_action",
			"next_action_date",
		],
		"submittable": True,
	},
}
TABLE_BY_DOCTYPE = {cfg["doctype"]: table for table, cfg in TABLES.items()}
DOCSTATUS_LABEL = {0: "Draft", 1: "Submitted", 2: "Cancelled"}


# ---------------------------------------------------------------------------
# TP Customer -> records
# ---------------------------------------------------------------------------


def push_to_records(customer):
	"""Called from TPCustomer.on_update."""
	before = customer.get_doc_before_save()
	frappe.flags.tp_customer_sync = True
	try:
		kept = {table: _upsert_rows(customer, table, cfg) for table, cfg in TABLES.items()}

		# Deletions last, dependants first (visits/turnover/production before plants).
		if before:
			for table in reversed(list(TABLES)):
				_delete_removed_rows(before, table, kept[table])
	finally:
		frappe.flags.tp_customer_sync = False


def _upsert_rows(customer, table, cfg):
	kept = set()
	for row in customer.get(table) or []:
		values = {f: row.get(f) for f in cfg["fields"]}
		_check_plant(customer, table, row, values)
		try:
			if row.record and frappe.db.exists(cfg["doctype"], row.record):
				record = frappe.get_doc(cfg["doctype"], row.record)
				if record.customer != customer.name:
					frappe.throw(_("{0} belongs to another customer.").format(row.record))
				changed = {f: v for f, v in values.items() if _norm(record.get(f)) != _norm(v)}
				if changed:
					# Submitted records only accept their "Allow on Submit" fields (e.g. a DVR's lead status / stage)
					if record.docstatus != 0 and not set(changed) <= _allowed_on_submit(cfg["doctype"]):
						frappe.throw(
							_("{0} is {1} and cannot be edited here. Open it to amend.").format(
								frappe.bold(record.name), _(DOCSTATUS_LABEL[record.docstatus])
							)
						)
					record.update(changed)
					record.save()
			else:
				record = frappe.get_doc({"doctype": cfg["doctype"], "customer": customer.name, **values}).insert()
				row.record = record.name
				row.db_set("record", record.name, update_modified=False)

			if cfg.get("submittable") and record.docstatus == 0 and row.submit_on_save:
				record.submit()
			_copy_back(row, record, cfg)
		except frappe.ValidationError as e:
			frappe.clear_messages()
			frappe.throw(_("{0} row #{1}: {2}").format(_(cfg["label"]), row.idx, cstr(e)))
		kept.add(record.name)
	return kept


def _delete_removed_rows(before, table, kept):
	cfg = TABLES[table]
	for old in before.get(table) or []:
		if not old.record or old.record in kept or not frappe.db.exists(cfg["doctype"], old.record):
			continue
		if cfg.get("submittable") and frappe.db.get_value(cfg["doctype"], old.record, "docstatus") == 1:
			frappe.throw(
				_("{0}: {1} is submitted and cannot be removed here. Cancel it from the visit itself.").format(
					_(cfg["label"]), frappe.bold(old.record)
				)
			)
		try:
			frappe.delete_doc(cfg["doctype"], old.record)
		except frappe.LinkExistsError:
			frappe.clear_messages()
			frappe.throw(
				_("{0}: {1} cannot be removed because other records (visits, wheel data, …) still use it.").format(
					_(cfg["label"]), frappe.bold(old.record)
				)
			)


def _copy_back(row, record, cfg):
	"""The record may adjust values on save (trimmed names, Won -> Order Received, …).
	Copy them back so the row matches its record, plus a DVR's status and stage %."""
	changes = {f: record.get(f) for f in cfg["fields"] if _norm(row.get(f)) != _norm(record.get(f))}
	if cfg.get("submittable"):
		changes.update(status=DOCSTATUS_LABEL[record.docstatus], stage_completed=record.stage_completed)
	if changes:
		row.update(changes)
		row.db_set(changes, update_modified=False)


def _check_plant(customer, table, row, values):
	plant = values.get("plant")
	if table != "plants" and plant and frappe.db.get_value("Plant", plant, "customer") != customer.name:
		frappe.throw(
			_("{0} row #{1}: plant {2} does not belong to this customer.").format(
				_(TABLES[table]["label"]), row.idx, frappe.bold(plant)
			)
		)


def _allowed_on_submit(doctype):
	return {df.fieldname for df in frappe.get_meta(doctype).fields if df.allow_on_submit}


def _norm(value):
	if isinstance(value, (int, float)):
		return flt(value)
	return cstr(value)


# ---------------------------------------------------------------------------
# records -> TP Customer
# ---------------------------------------------------------------------------


def on_record_change(doc, method=None):
	"""doc_events hook for the synced doctypes."""
	if frappe.flags.tp_customer_sync:
		return
	customers = {doc.get("customer")}
	before = doc.get_doc_before_save() if method == "on_update" else None
	if before:
		customers.add(before.get("customer"))  # record moved to another customer
	for customer in customers:
		if customer and frappe.db.exists("TP Customer", customer):
			pull_from_records(customer, [TABLE_BY_DOCTYPE[doc.doctype]])


def pull_from_records(customer, tables=None):
	"""Rebuild the customer's child tables from the real records."""
	for table in tables or TABLES:
		cfg = TABLES[table]
		submittable = cfg.get("submittable")
		fields = ["name", *cfg["fields"]] + (["docstatus", "stage_completed"] if submittable else [])
		filters = {"customer": customer}
		if submittable:
			filters["docstatus"] = ("<", 2)  # cancelled visits drop off the tab
		records = frappe.get_all(cfg["doctype"], filters=filters, fields=fields, order_by="creation asc")

		frappe.db.delete(cfg["child"], {"parent": customer, "parenttype": "TP Customer", "parentfield": table})
		for idx, r in enumerate(records, 1):
			row = {f: r.get(f) for f in cfg["fields"]}
			if submittable:
				row.update(
					status=DOCSTATUS_LABEL[r.docstatus],
					stage_completed=r.stage_completed,
					submit_on_save=1 if r.docstatus == 1 else 0,
				)
			frappe.get_doc(
				{
					"doctype": cfg["child"],
					"parent": customer,
					"parenttype": "TP Customer",
					"parentfield": table,
					"idx": idx,
					"record": r.name,
					**row,
				}
			).db_insert()
	# An open customer form is now out of date; bumping `modified` makes Frappe
	# ask the user to reload instead of saving stale rows over the change.
	frappe.db.set_value("TP Customer", customer, "modified", now_datetime(), update_modified=False)
