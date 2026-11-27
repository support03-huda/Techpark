// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// Opportunity colour by result, else by stage; overdue next action in red.

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);

frappe.listview_settings["TP Opportunity"] = {
	add_fields: ["status", "stage", "lead_status", "next_action_date", "importance"],
	get_indicator(doc) {
		if (doc.lead_status === "Won") return [__(doc.status || "Won"), "green", "lead_status,=,Won"];
		if (doc.lead_status === "Lost") return [__(doc.status || "Lost"), "red", "lead_status,=,Lost"];
		if (doc.lead_status === "On Hold") return [__("On Hold"), "gray", "lead_status,=,On Hold"];
		if (doc.next_action_date && doc.next_action_date < frappe.datetime.get_today()) {
			return [__("Overdue: {0}", [__(doc.status || "")]), "red", "next_action_date,<,Today"];
		}
		if (!doc.status) return [__("No Visit Yet"), "gray"];
		return [__(doc.status), techpark.colour("TP Stage", doc.stage, "orange"), "status,=," + doc.status]; // 2026-11-27: stage master's Colour
	},
};
