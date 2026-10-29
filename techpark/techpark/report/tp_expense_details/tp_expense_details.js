// Copyright (c) 2026, Techpark International
// Filters of the Expense Details report (every bill of every expense).

frappe.query_reports["TP Expense Details"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "User" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "\nDraft\nPending Manager\nPending Admin\nApproved" },
		{ fieldname: "expense_type", label: __("Expense Type"), fieldtype: "Link", options: "TP Expense Type" },
	],

	onload(report) {
		report.page.add_inner_button(__("Export"), () => report.export_report());
	},

	// Status in the colour of the expense list.
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data && data.status) {
			const color = { Draft: "gray", "Pending Manager": "orange", "Pending Admin": "blue", Approved: "green" }[data.status];
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
