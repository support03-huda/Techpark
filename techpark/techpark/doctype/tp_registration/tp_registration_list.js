frappe.listview_settings["TP Registration"] = {
	get_indicator(doc) {
		const colors = { Pending: "orange", Approved: "green", Rejected: "red" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
