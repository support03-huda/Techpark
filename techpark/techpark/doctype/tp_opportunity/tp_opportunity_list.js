// Copyright (c) 2026, Techpark International
// Opportunity colour by result, else by stage; overdue next action in red.

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
		return [__(doc.status), doc.stage === "Sales" ? "blue" : "orange", "status,=," + doc.status];
	},
};
