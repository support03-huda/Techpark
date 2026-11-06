// Copyright (c) 2026, Techpark International
// Opportunity: open its visits, or add a visit for this application line.

frappe.provide("techpark");

frappe.ui.form.on("TP Opportunity", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("New Visit"), () => {
			// Picked up by the visit form on load (daily_visit_report.js)
			techpark.new_visit_row = {
				application: frm.doc.application,
				principal: frm.doc.principal,
				supplier_product_category: frm.doc.supplier_product_category,
				spec: frm.doc.spec,
				size: frm.doc.size,
			};
			frappe.new_doc("Daily Visit Report", { customer: frm.doc.customer });
		});
	},
});
