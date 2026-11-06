// Copyright (c) 2026, Techpark International
// Opened from a visit's "Create a new Technical Lead": after saving, Frappe returns to that
// visit and puts this lead in the row it was created from.

frappe.ui.form.on("TP Technical Lead", {
	setup(frm) {
		frm.set_query("principal", () => ({ filters: { is_active: 1 } }));
		frm.set_query("supplier_product_category", () => ({
			filters: { principal: frm.doc.principal || "", is_active: 1 },
		}));
	},
	principal(frm) {
		frm.set_value("supplier_product_category", "");
	},
});
