// Last edited: 2026-11-27
// Indicator: the visit's stage (Development / Sales), with Won / Lost / On Hold called out.
// 2026-11-27: stage colour = the TP Stage master's Colour (stages can be renamed)

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);
frappe.listview_settings["Daily Visit Report"] = {
	add_fields: ["lead_status", "dvr_stage", "docstatus"],
	get_indicator(doc) {
		const stage = doc.dvr_stage || techpark.K("TP Stage", "Development");
		const stage_filter = `dvr_stage,=,${stage}`;
		if (doc.docstatus === 0) return [__("Draft") + " · " + __(stage), "gray", "docstatus,=,0"];
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		if (doc.lead_status === "Won") return [__(techpark.K("TP Stage", "Sales")) + " · " + __("Won"), "green", "lead_status,=,Won"];
		if (doc.lead_status === "Lost") return [__(stage) + " · " + __("Lost"), "red", "lead_status,=,Lost"];
		if (doc.lead_status === "On Hold") return [__(stage) + " · " + __("On Hold"), "gray", "lead_status,=,On Hold"];
		return [__(stage) + " " + __("Stage"), techpark.colour("TP Stage", stage, "orange"), stage_filter];
	},
};
