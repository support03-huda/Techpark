"""Principal-wise Status on every visit, and DVR Type / Department / Principals on the customers'
Visits tab rows, so the tab matches its visits (otherwise saving a customer would see a change on a
submitted visit and refuse)."""

import frappe


def execute():
	# Product categories are numbered: keep their name on the row for display.
	frappe.db.sql(
		"""
		update `tabDVR Principal` r
		join `tabSupplier Product Category` c on c.name = r.supplier_product_category
		set r.category_name = c.category_name
		"""
	)
	rows = frappe.get_all(
		"DVR Principal",
		filters={"parenttype": "Daily Visit Report"},
		fields=["parent", "principal", "category_name", "development_status", "sales_status"],
		order_by="parent, idx",
	)
	summary = {}
	for r in rows:
		label = " · ".join(p for p in (r.principal, r.category_name) if p)
		summary.setdefault(r.parent, []).append(f"{label}: {r.sales_status or r.development_status or ''}")
	for visit, lines in summary.items():
		frappe.db.set_value("Daily Visit Report", visit, "principal_summary", "\n".join(lines), update_modified=False)

	frappe.db.sql(
		"""
		update `tabTP Customer Visit` row
		join `tabDaily Visit Report` dvr on dvr.name = row.record
		set row.dvr_type = dvr.dvr_type, row.department = dvr.department, row.principal_summary = dvr.principal_summary
		where row.parenttype = 'TP Customer'
		"""
	)
