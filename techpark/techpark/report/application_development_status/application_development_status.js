// Copyright (c) 2026, Techpark International

frappe.query_reports["Application Development Status"] = {
	filters: [
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "TP Customer" },
		{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
		{ fieldname: "visited_by", label: __("Sales Person"), fieldtype: "Link", options: "User" },
		{ fieldname: "importance", label: __("Importance"), fieldtype: "Select", options: "\nHigh\nMedium\nLow" },
		{ fieldname: "stage", label: __("Stage"), fieldtype: "Select", options: "\nDevelopment\nSales" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				"",
				"Introduction",
				"Enquiry Received",
				"Sent to Principal",
				"Offer Received",
				"Offer Submitted",
				"Trial PO Received",
				"Sample Received",
				"Trial in Progress",
				"Retest",
				"Successful Trial",
				"Trial Failed",
				"Bulk Trial PO",
				"Enquiry Follow-up",
				"Order Follow-up",
				"Delivery Follow-up",
				"Payment Follow-up",
				"Regularization",
				"On Hold",
				"Cancelled",
			].join("\n"),
		},
		{ fieldname: "lead_status", label: __("Result"), fieldtype: "Select", options: "\nOpen\nWon\nLost\nOn Hold" },
		{ fieldname: "open_only", label: __("Open Only (not Won / Lost)"), fieldtype: "Check", default: 1 },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "follow_up" && data) {
			const color = { Overdue: "red", "Due Soon": "orange", Planned: "blue" }[data.follow_up];
			if (color) value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (column.fieldname === "stage" && data && data.stage) {
			value = `<span class="indicator-pill ${data.stage === "Sales" ? "green" : "blue"}">${value}</span>`;
		}
		// Milestone columns coloured like the client's Development Status sheet
		const milestone = {
			Successful: "green", Regularised: "green", Received: "blue", Supplied: "blue", "Received / Sent": "blue",
			"Can Use as Samples": "blue", "In Progress": "orange", "To Try": "orange", Failed: "red",
			"Cost Problem": "red", "Not Regularised": "red", "Not Tried": "gray",
		};
		if (["samples", "trials", "bulk_trial_po", "regularised"].includes(column.fieldname) && data && data[column.fieldname]) {
			value = `<span class="indicator-pill ${milestone[data[column.fieldname]] || "gray"}">${value}</span>`;
		}
		if (column.fieldname === "importance" && data && data.importance) {
			const color = { High: "red", Medium: "orange", Low: "gray" }[data.importance];
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
