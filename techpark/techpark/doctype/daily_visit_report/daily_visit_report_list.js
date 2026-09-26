frappe.listview_settings["Daily Visit Report"] = {
	add_fields: ["lead_status", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		const colors = { Prospect: "orange", Won: "green", Lost: "red", "On Hold": "gray" };
		return [__(doc.lead_status), colors[doc.lead_status] || "blue", `lead_status,=,${doc.lead_status}`];
	},
};
