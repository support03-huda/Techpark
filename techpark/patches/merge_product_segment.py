# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
"""Product Segment and Industry Domain were the same thing: every Segment field now picks from the
Industry Segment (Industry Domain) master. Old Product Segment ids become Industry Segment names, and a
Product without an Industry Segment gets the one from its old Segment.
A Customer's Industry Segment is a multi-select: its old single Industry Domain is added to it."""

import frappe

FIELDS = [
	("Customer Segment Application", "segment"),
	("Organizaton Segment", "segment"),
	("Segment Split", "segment"),
	("TP Customer Segment", "segment"),
	("TP Customer Wheel Spec", "segment"),
	("Wheel Specification", "segment"),
	("Customer Product", "segment"),
]


def execute():
	if not frappe.db.table_exists("Product Segment"):
		return
	names = {}
	for seg in frappe.get_all("Product Segment", fields=["name", "segment_name", "is_active"]):
		title = (seg.segment_name or "").strip()
		if not title:
			continue
		if not frappe.db.exists("Industry Segment", title):
			frappe.get_doc({"doctype": "Industry Segment", "industry_name": title, "is_active": seg.is_active}).insert(
				ignore_permissions=True
			)
		names[str(seg.name)] = title

	for doctype, fieldname in FIELDS:
		for old, new in names.items():
			frappe.db.sql(
				f"update `tab{doctype}` set `{fieldname}` = %s where `{fieldname}` = %s", (new, old)
			)

	frappe.db.sql(
		"""update `tabCustomer Product` set industry_domain = segment
		where ifnull(industry_domain, '') = '' and ifnull(segment, '') != ''"""
	)

	# Customer: the old single Industry Domain goes first in the Industry Segment multi-select
	for c in frappe.get_all("TP Customer", filters={"industry_domain": ("is", "set")}, fields=["name", "industry_domain"]):
		if frappe.db.exists("Organizaton Segment", {"parenttype": "TP Customer", "parent": c.name, "segment": c.industry_domain}):
			continue
		frappe.db.sql(
			"update `tabOrganizaton Segment` set idx = idx + 1 where parenttype = 'TP Customer' and parent = %s", c.name
		)
		frappe.get_doc(
			{
				"doctype": "Organizaton Segment",
				"parent": c.name,
				"parenttype": "TP Customer",
				"parentfield": "segments",
				"idx": 1,
				"segment": c.industry_domain,
			}
		).db_insert()

	# ...and the customer's main segment is the first one
	for row in frappe.db.sql(
		"""select s.parent, s.segment from `tabOrganizaton Segment` s
		join `tabTP Customer` c on c.name = s.parent
		where s.parenttype = 'TP Customer' and ifnull(c.industry_domain, '') = '' and ifnull(s.segment, '') != ''
		order by s.parent, s.idx""",
		as_dict=True,
	):
		if not frappe.db.get_value("TP Customer", row.parent, "industry_domain"):
			frappe.db.set_value("TP Customer", row.parent, "industry_domain", row.segment, update_modified=False)
