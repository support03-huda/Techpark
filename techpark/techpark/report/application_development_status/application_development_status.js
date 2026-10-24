// Copyright (c) 2026, Techpark International

frappe.query_reports["Application Development Status"] = {
	filters: [
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "TP Customer" },
		{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
		{ fieldname: "visited_by", label: __("Salesperson"), fieldtype: "Link", options: "User" },
		{
			fieldname: "lead_status",
			label: __("Lead Status"),
			fieldtype: "Select",
			options: "\nProspect\nWon\nLost\nOn Hold",
		},
		{ fieldname: "open_only", label: __("Open Only (not Won / Lost)"), fieldtype: "Check", default: 1 },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "follow_up" && data) {
			const color = { Overdue: "red", "Due Soon": "orange", Planned: "blue" }[data.follow_up];
			if (color) value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
