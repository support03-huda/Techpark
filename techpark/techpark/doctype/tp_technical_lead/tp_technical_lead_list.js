// Last edited: 2026-11-26
// Copyright (c) 2026, Techpark International
// 2026-11-26: the list shows where each lead stands: Development, Sales (regularised) or Closed (failed)
frappe.listview_settings["TP Technical Lead"] = {
	add_fields: ["stage", "is_closed", "progress"],
	get_indicator(doc) {
		if (doc.is_closed) return [__("Closed"), "red", "is_closed,=,1"];
		if (doc.stage) return [__(doc.stage), doc.stage === "Sales" ? "blue" : "orange", `stage,=,${doc.stage}`];
		return [__("Not Visited"), "gray", "stage,is,not set"];
	},
};
