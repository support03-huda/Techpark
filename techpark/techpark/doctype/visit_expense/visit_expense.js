// Copyright (c) 2026, Techpark International
frappe.ui.form.on("Visit Expense", {
	setup(frm) {
		frm.set_query("daily_visit_report", () => ({ filters: { docstatus: ["<", 2] } }));
	},

	refresh(frm) {
		if (frm.doc.daily_visit_report) {
			frm.add_custom_button(__("Open DVR"), () => frappe.set_route("Form", "Daily Visit Report", frm.doc.daily_visit_report));
		}
	},
});
