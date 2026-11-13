// Copyright (c) 2026, Techpark International
// Application Wise Status: an application of the common list per group row, its customers under it.

frappe.query_reports["Application Wise Status"] = {
	filters: [
		{ fieldname: "industry_domain", label: __("Industry"), fieldtype: "Link", options: "Industry Domain" },
		{ fieldname: "product", label: __("Product"), fieldtype: "Link", options: "Customer Product" },
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
	initial_depth: 1,

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (data.is_group && column.fieldname === "label") return `<b>${value}</b>`;
		if (data.is_group && ["demand", "customers", "stage"].includes(column.fieldname)) return `<b>${value}</b>`;
		if (column.fieldname === "stage" && !data.is_group && data.stage) {
			const color = data.stage === "Sales" ? "blue" : "orange";
			return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.stage))}</span>`;
		}
		if (column.fieldname === "progress" && !data.is_group && data.progress) {
			const color = { Approved: "green", "Evaluation Failed": "red", "Not Started": "gray", Quoted: "orange" }[data.progress] || "blue";
			return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.progress))}</span>`;
		}
		return value;
	},
};
