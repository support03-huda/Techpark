# Last edited: 2026-11-25
# Copyright (c) 2026, Techpark International
# 2026-11-25: one development line per Technical Lead (client): merge the lines that share a lead
"""A lead whose category / spec changed between visits got a second TP Opportunity. Merge them into
one (the lead's own, else the oldest): visits, the lead and every other link move over, then the line
is rebuilt from all its visits. Lines without visits (imported) are left as they are."""

import frappe
from frappe.model.rename_doc import rename_doc

from techpark.opportunity import refresh_opportunity

KEEP_FIELDS = ("importance", "remarks", "invoice_oc", "notion_page_url", "notion_pushed_on")


def execute():
	rows = frappe.db.sql(
		"""select distinct r.technical_lead, r.opportunity from `tabDVR Principal` r
		join `tabTP Opportunity` o on o.name = r.opportunity
		where r.parenttype = 'Daily Visit Report' and ifnull(r.technical_lead, '') != ''
		order by o.creation""",
		as_dict=True,
	)
	by_lead = {}
	for r in rows:
		by_lead.setdefault(r.technical_lead, [])
		if r.opportunity not in by_lead[r.technical_lead]:
			by_lead[r.technical_lead].append(r.opportunity)

	for lead, names in by_lead.items():
		names = [n for n in names if frappe.db.exists("TP Opportunity", n)]
		if len(names) < 2:
			continue
		own = frappe.db.get_value("TP Technical Lead", lead, "opportunity")
		keep = own if own in names else names[0]
		keeper = frappe.db.get_value("TP Opportunity", keep, KEEP_FIELDS, as_dict=True)
		for old in names:
			if old == keep:
				continue
			values = frappe.db.get_value("TP Opportunity", old, KEEP_FIELDS, as_dict=True)
			fill = {f: values[f] for f in KEEP_FIELDS if values.get(f) and not keeper.get(f)}
			if fill:
				frappe.db.set_value("TP Opportunity", keep, fill, update_modified=False)
				keeper.update(fill)
			rename_doc(
				"TP Opportunity", old, keep, merge=True, force=True, ignore_permissions=True, show_alert=False, rebuild_search=False
			)
		refresh_opportunity(keep)
