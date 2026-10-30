"""Stage (Development / Sales / Development + Sales) on every visit, from its principal rows."""

import frappe


def execute():
	frappe.db.sql(
		"""
		update `tabDaily Visit Report` dvr
		join (
			select parent,
				case
					when sum(stage = 'Sales') = 0 then 'Development'
					when sum(stage = 'Sales') = count(*) then 'Sales'
					else 'Development + Sales'
				end as dvr_stage
			from `tabDVR Principal`
			where parenttype = 'Daily Visit Report'
			group by parent
		) r on r.parent = dvr.name
		set dvr.dvr_stage = r.dvr_stage
		"""
	)
