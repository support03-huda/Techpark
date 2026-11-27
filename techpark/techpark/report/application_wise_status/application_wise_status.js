// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// Application Wise Status: Industry Segment -> Product -> Application -> its customers.

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);

frappe.query_reports["Application Wise Status"] = {
	filters: [
		{ fieldname: "industry_domain", label: __("Industry/Product Segment"), fieldtype: "Link", options: "Industry Segment" }, // 2026-11-21: label per client
		{
			fieldname: "product", label: __("Product"), fieldtype: "Link", options: "Customer Product",
			get_query: () => {
				const industry = frappe.query_report.get_filter_value("industry_domain");
				return { filters: industry ? { industry_domain: industry } : {} };
			},
		},
		{ fieldname: "application", label: __("Application"), fieldtype: "Link", options: "Customer Application" },
		{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "TP Customer" },
		{ fieldname: "stage", label: __("Stage"), fieldtype: "Select", options: "\nDevelopment\nSales" },
		{
			fieldname: "progress", label: __("Progress"), fieldtype: "Select",
			options: "\nNot Started\nQuoted\nTrial Order Received\nUnder Trial\nApproved\nEvaluation Failed",
		},
		{ fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "User" },
	],
	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 2,

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (data.is_group && column.fieldname === "label") return `<b>${value}</b>`;
		if (data.is_group && ["demand", "customers", "stage"].includes(column.fieldname)) return `<b>${value}</b>`;
		if (column.fieldname === "stage" && !data.is_group && data.stage) {
			const color = techpark.colour("TP Stage", data.stage, "orange"); // 2026-11-27: stage master's Colour
			return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.stage))}</span>`;
		}
		if (column.fieldname === "progress" && !data.is_group && data.progress) {
			const color = techpark.colour("TP Lead Progress", data.progress, "blue"); // 2026-11-27: Lead Progress master's Colour
			return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.progress))}</span>`;
		}
		return value;
	},
};
