# Copyright (c) 2026, Techpark International
"""One application line per visit: fill the visit's new line fields from its first principal row."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabDaily Visit Report` d
		join `tabDVR Principal` r on r.parent = d.name and r.parenttype = 'Daily Visit Report'
			and r.parentfield = 'principals' and r.idx = 1
		set d.technical_lead = r.technical_lead, d.application = r.application, d.spec = r.spec, d.size = r.size,
			d.development_status = r.development_status, d.sales_status = r.sales_status,
			d.development_done_before = r.development_done_before, d.opportunity = r.opportunity
		where ifnull(d.application, '') = ''
		"""
	)
