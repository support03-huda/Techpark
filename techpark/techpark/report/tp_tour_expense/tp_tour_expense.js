// Copyright (c) 2026, Techpark International
// Tour Expense statement: bills grouped by expense head with a total per head and a head-wise summary.

frappe.query_reports["TP Tour Expense"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "User", default: frappe.session.user },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "\nDraft\nPending Manager\nPending Admin\nApproved" },
	],

	onload(report) {
		report.page.add_inner_button(__("Export"), () => report.export_report());
	},

	// Head rows bold on a tint, totals bold, the grand total highlighted.
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (data.is_head) {
			return column.fieldname === "expense_head"
				? `<b style="color: var(--heading-color); font-size: 13px;">${value}</b>`
				: value;
		}
		if (data.is_grand_total) return `<b style="color: var(--green-600, #2f9e44);">${value}</b>`;
		if (data.is_total) return `<b>${value}</b>`;
		return value;
	},
};
