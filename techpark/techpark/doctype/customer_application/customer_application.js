// Last edited: 2026-11-13
// Copyright (c) 2026, SWSPL and contributors
// Industry Segment -> Product -> Application: the Product list shows the segment's products only.

frappe.ui.form.on("Customer Application", {
	setup(frm) {
		frm.set_query("product", () => ({
			filters: frm.doc.industry_domain ? { industry_domain: frm.doc.industry_domain } : {},
		}));
	},
	industry_domain(frm) {
		if (!frm.doc.product || !frm.doc.industry_domain) return;
		frappe.db.get_value("Customer Product", frm.doc.product, "industry_domain").then((r) => {
			const industry = r.message && r.message.industry_domain;
			if (industry && industry !== frm.doc.industry_domain) frm.set_value("product", "");
		});
	},
});
