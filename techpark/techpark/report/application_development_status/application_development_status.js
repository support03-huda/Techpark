// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);

// 2026-11-27: master colours (also in public/js/techpark.js)
frappe.provide("techpark");
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");

frappe.query_reports["Application Development Status"] = {
	filters: [
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "TP Customer" },
		{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
		{ fieldname: "visited_by", label: __("Sales Person"), fieldtype: "Link", options: "User" },
		{ fieldname: "importance", label: __("Priority"), fieldtype: "Link", options: "TP Priority" }, // 2026-11-27: label Priority (client); // 2026-11-26: master
		{ fieldname: "stage", label: __("Stage"), fieldtype: "Link", options: "TP Stage" }, // 2026-11-27: the master (renameable)
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "", // 2026-11-27: every status of the masters, filled on load (was a fixed list)
		},
		// 2026-11-26: the Status list also has the statuses added to the masters (onload)
		{ fieldname: "lead_status", label: __("Result"), fieldtype: "Select", options: "\nOpen\nWon\nLost\nOn Hold" },
		{ fieldname: "open_only", label: __("Open Only (not Won / Lost)"), fieldtype: "Check", default: 1 },
	],

	// 2026-11-26: Development / Sales Status are masters: the Status filter lists them all
	onload(report) {
		frappe.xcall("techpark.statuses.get_status_progress").then((map) => {
			const f = report.get_filter("status");
			if (!f || !map) return;
			f.df.options = ["", ...Object.keys(map)].join("\n");
			f.refresh();
		});
	},

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "follow_up" && data) {
			const color = { Overdue: "red", "Due Soon": "orange", Planned: "blue" }[data.follow_up];
			if (color) value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (column.fieldname === "stage" && data && data.stage) {
			value = `<span class="indicator-pill ${techpark.colour("TP Stage", data.stage, "blue")}">${value}</span>`;
		}
		// 2026-11-27: milestone colour = the master's Colour (the values can be renamed)
		const MILESTONE_MASTER = { samples: "TP Sample Status", trials: "TP Trial Status", bulk_trial_po: "TP Bulk Trial PO Status", regularised: "TP Regularised Status" };
		if (MILESTONE_MASTER[column.fieldname] && data && data[column.fieldname]) {
			value = `<span class="indicator-pill ${techpark.colour(MILESTONE_MASTER[column.fieldname], data[column.fieldname])}">${value}</span>`;
		}
		if (column.fieldname === "importance" && data && data.importance) {
			const color = techpark.colour("TP Priority", data.importance); // 2026-11-27: TP Priority master's Colour
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
