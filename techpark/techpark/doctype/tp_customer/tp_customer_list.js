// Last edited: 2026-11-23
frappe.listview_settings["TP Customer"] = {
	add_fields: ["customer_status"],
	get_indicator(doc) {
		const colors = { "Active Customer": "green", Prospect: "orange", Inactive: "red" };
		if (doc.customer_status) {
			return [__(doc.customer_status), colors[doc.customer_status] || "gray", `customer_status,=,${doc.customer_status}`];
		}
	},
	// 2026-11-23: the Status column header sorted by the pseudo field "status_field" -> Frappe 16 error
	// "You do not have permission to access field: TP Customer.status_field". Sort by customer_status instead.
	onload(listview) {
		const fix = () => {
			for (const col of listview.columns || []) {
				if (col.type === "Status" && col.df?.fieldname === "status_field") col.df = { ...col.df, fieldname: "customer_status" };
			}
		};
		const setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = () => {
			setup_columns();
			fix();
		};
		fix();
		listview.render_header(true);
		// 2026-11-23: a sort saved by the failed click would keep breaking the list
		if (listview.sort_by === "status_field") {
			listview.sort_selector.set_value("modified", "desc");
			listview.on_sort_change("modified", "desc");
		}
	},
};
