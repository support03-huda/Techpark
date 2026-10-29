// Copyright (c) 2026, Techpark International
// Expense claim: own user filled in, bills limited to own visits and active expense types, the customer
// taken from the visit, a running total, and the buttons of the approval steps
// Draft -> Pending Manager -> Pending Admin -> Approved (decided on the server: TPExpense.allowed_actions).

frappe.provide("techpark.expense");

techpark.expense.ADMIN_ROLES = ["TechPark Approver", "System Manager"];

frappe.ui.form.on("TP Expense", {
	setup(frm) {
		frm.set_query("expense_type", "items", () => ({ filters: { inactive: 0 } }));
		frm.set_query("visit", "items", () => ({
			filters: { visited_by: frm.doc.employee || frappe.session.user, docstatus: ["<", 2] },
		}));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.employee) frm.set_value("employee", frappe.session.user);
	},

	refresh(frm) {
		const is_admin = frappe.user.has_role(techpark.expense.ADMIN_ROLES);
		// Only an approver may enter an expense for somebody else.
		frm.set_df_property("employee", "read_only", is_admin ? 0 : 1);
		if (frm.is_new()) return;

		if (
			frm.doc.status === "Approved" ||
			frm.doc.status === "Pending Manager" ||
			(frm.doc.status === "Pending Admin" && !is_admin)
		) {
			frm.disable_save();
			frm.set_read_only();
			frm.refresh_fields();
		}

		const actions = (frm.doc.__onload && frm.doc.__onload.actions) || [];
		if (actions.includes("send_for_approval")) {
			frm.add_custom_button(__("Send for Approval"), () =>
				techpark.expense.run(frm, "send_for_approval", {}, __("After sending you can no longer change this expense. Send it for approval?"))
			).addClass("btn-primary");
		}
		if (actions.includes("approve")) {
			const question =
				frm.doc.status === "Pending Manager"
					? __("Approve this expense and send it to the approver?")
					: __("Give the final approval for {0}?", [format_currency(frm.doc.passed_amount)]);
			frm.add_custom_button(__("Approve"), () => techpark.expense.run(frm, "approve", {}, question)).addClass("btn-primary");
		}
		if (actions.includes("reject")) {
			frm.add_custom_button(__("Reject"), () => techpark.expense.reject(frm)).addClass("btn-danger");
		}
		if (actions.includes("unapprove")) {
			frm.add_custom_button(__("Unapprove"), () => techpark.expense.run(frm, "unapprove"), __("Actions"));
		}
	},

	// Visits of another employee no longer fit.
	employee(frm) {
		(frm.doc.items || []).forEach((row) => {
			if (row.visit) frappe.model.set_value(row.doctype, row.name, "visit", "");
		});
	},
});

frappe.ui.form.on("TP Expense Item", {
	items_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "expense_date", frm.doc.entry_date);
	},
	// The bill is for the customer of the visit.
	visit(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.visit || row.customer) return;
		frappe.db.get_value("Daily Visit Report", row.visit, "customer").then((r) => {
			if (r.message && r.message.customer) frappe.model.set_value(cdt, cdn, "customer", r.message.customer);
		});
	},
	amount(frm) {
		techpark.expense.set_totals(frm);
	},
	passed_amount(frm) {
		techpark.expense.set_totals(frm);
	},
	items_remove(frm) {
		techpark.expense.set_totals(frm);
	},
});

// Totals while the bills are typed; the server works them out again on save.
techpark.expense.set_totals = function (frm) {
	const items = frm.doc.items || [];
	// Until the approver's step every bill is passed in full.
	const follow = frm.doc.status === "Draft" || frm.doc.status === "Pending Manager";
	frm.set_value("total_amount", items.reduce((sum, row) => sum + flt(row.amount), 0));
	frm.set_value("passed_amount", items.reduce((sum, row) => sum + flt(follow ? row.amount : row.passed_amount), 0));
};

techpark.expense.reject = function (frm) {
	frappe.prompt(
		{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
		(values) => techpark.expense.run(frm, "reject", { reason: values.reason }),
		__("Reject Expense"),
		__("Reject")
	);
};

// Save unsaved changes, ask when a question is given, then run an approval step and show the result.
techpark.expense.run = function (frm, method, args, question) {
	const run = () =>
		(frm.is_dirty() ? frm.save() : Promise.resolve())
			.then(() => frm.call(method, args || {}))
			.then(() => frm.reload_doc());
	question ? frappe.confirm(question, run) : run();
};
