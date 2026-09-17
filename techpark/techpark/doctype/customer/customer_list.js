frappe.listview_settings["Customer"] = {
	add_fields: ["customer_status"],
	get_indicator(doc) {
		const colors = { "Active Customer": "green", Prospect: "orange", Inactive: "red" };
		if (doc.customer_status) {
			return [__(doc.customer_status), colors[doc.customer_status] || "gray", `customer_status,=,${doc.customer_status}`];
		}
	},
};
