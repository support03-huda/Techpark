// Copyright (c) 2026, Techpark International
frappe.ui.form.on("Plant", {
	refresh(frm) {
		if (frm.doc.customer) {
			frm.add_custom_button(__("Open Customer"), () => frappe.set_route("Form", "TP Customer", frm.doc.customer));
		}
	},
});
