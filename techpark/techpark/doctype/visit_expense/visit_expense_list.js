frappe.listview_settings["Visit Expense"] = {
	add_fields: ["approval_status"],
	get_indicator(doc) {
		const colors = { Pending: "orange", Approved: "green", Rejected: "red" };
		return [__(doc.approval_status), colors[doc.approval_status] || "gray", `approval_status,=,${doc.approval_status}`];
	},
};
