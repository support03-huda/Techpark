// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// 2026-11-26: the list shows where each lead stands: Development, Sales (regularised) or Closed (failed)
frappe.listview_settings["TP Technical Lead"] = {
	add_fields: ["stage", "is_closed", "progress", "is_frozen"],
	get_indicator(doc) {
		if (doc.is_closed) return [__("Closed"), "red", "is_closed,=,1"];
		if (doc.is_frozen) return [__("Frozen") + (doc.stage ? " · " + __(doc.stage) : ""), "purple", "is_frozen,=,1"]; // 2026-11-27
		if (doc.stage) return [__(doc.stage), doc.stage === "Sales" ? "blue" : "orange", `stage,=,${doc.stage}`];
		return [__("Not Visited"), "gray", "stage,is,not set"];
	},
};
