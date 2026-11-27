// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// 2026-11-26: the list shows where each lead stands: Development, Sales (regularised) or Closed (failed)

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);
frappe.listview_settings["TP Technical Lead"] = {
	add_fields: ["stage", "is_closed", "progress", "is_frozen"],
	get_indicator(doc) {
		if (doc.is_closed) return [__("Closed"), "red", "is_closed,=,1"];
		if (doc.is_frozen) return [__("Frozen") + (doc.stage ? " · " + __(doc.stage) : ""), "purple", "is_frozen,=,1"]; // 2026-11-27
		if (doc.stage) return [__(doc.stage), techpark.colour("TP Stage", doc.stage, "orange"), `stage,=,${doc.stage}`]; // 2026-11-27
		return [__("Not Visited"), "gray", "stage,is,not set"];
	},
};
