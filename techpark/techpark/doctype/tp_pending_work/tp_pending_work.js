// Copyright (c) 2026, Techpark International

frappe.ui.form.on("TP Pending Work", {
	setup(frm) {
		frm.set_query("opportunity", () => ({ filters: frm.doc.customer ? { customer: frm.doc.customer } : {} }));
		// Table MultiSelect: the query goes on the field itself (it has no grid)
		frm.set_query("responsible", () => ({ filters: { enabled: 1, user_type: "System User" } }));
	},
	refresh(frm) {
		if (frm.is_new() || ["Done", "Cancelled"].includes(frm.doc.status)) return;
		frm.add_custom_button(__("Mark Done"), () => frm.set_value("status", "Done").then(() => frm.save()));
		const overdue = frm.doc.due_date && frm.doc.due_date < frappe.datetime.get_today();
		if (overdue) frm.dashboard.set_headline(`<span class="text-danger">${__("Overdue since {0}", [frappe.datetime.str_to_user(frm.doc.due_date)])}</span>`);
	},
	opportunity(frm) {
		if (!frm.doc.opportunity) return;
		frappe.db.get_value("TP Opportunity", frm.doc.opportunity, ["customer", "principal"]).then(({ message: o }) => {
			if (o && !frm.doc.customer) frm.set_value("customer", o.customer);
			if (o && !frm.doc.principal) frm.set_value("principal", o.principal);
		});
	},
});
