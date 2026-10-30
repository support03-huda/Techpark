// Indicator: the visit's stage (Development / Sales), with Won / Lost / On Hold called out.
// Colours match techpark.dvr.STAGE_COLORS in daily_visit_report.js.
frappe.listview_settings["Daily Visit Report"] = {
	add_fields: ["lead_status", "dvr_stage", "docstatus"],
	get_indicator(doc) {
		const stage = doc.dvr_stage || "Development";
		const stage_filter = `dvr_stage,=,${stage}`;
		if (doc.docstatus === 0) return [__("Draft") + " · " + __(stage), "gray", "docstatus,=,0"];
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		if (doc.lead_status === "Won") return [__("Sales") + " · " + __("Won"), "green", "lead_status,=,Won"];
		if (doc.lead_status === "Lost") return [__(stage) + " · " + __("Lost"), "red", "lead_status,=,Lost"];
		if (doc.lead_status === "On Hold") return [__(stage) + " · " + __("On Hold"), "gray", "lead_status,=,On Hold"];
		const colors = { Development: "orange", Sales: "blue", "Development + Sales": "yellow" };
		return [__(stage + " Stage"), colors[stage] || "orange", stage_filter];
	},
};
