// Copyright (c) 2026, Techpark International
// Expense list, shown as My Expenses (filtered to the logged-in user): colour of the status, and
// Send for Approval / Approve / Unapprove on the selected expenses.

const TP_EXPENSE_COLORS = { Draft: "gray", "Pending Manager": "orange", "Pending Admin": "blue", Approved: "green" };

frappe.listview_settings["TP Expense"] = {
	add_fields: ["status", "employee"],

	get_indicator(doc) {
		return [__(doc.status), TP_EXPENSE_COLORS[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		// This list is "My Expenses"; the team's expenses are on the Expense Approvals page.
		listview.page.set_title(__("My Expenses"));
		if (!listview.filter_area.get().some((filter) => filter[1] === "employee")) {
			listview.filter_area.add([["TP Expense", "employee", "=", frappe.session.user]]);
		}
		listview.page.add_actions_menu_item(__("Send for Approval"), () => tp_expense_bulk_action(listview, "send_for_approval"), false);
		// Only managers with a team and approvers; the server still skips what the user may not approve.
		if (frappe.boot.techpark_expense_approver) {
			listview.page.add_actions_menu_item(__("Approve"), () => tp_expense_bulk_action(listview, "approve"), false);
		}
		if (frappe.user.has_role(["TechPark Approver", "System Manager"])) {
			listview.page.add_actions_menu_item(__("Unapprove"), () => tp_expense_bulk_action(listview, "unapprove"), false);
		}
	},
};

function tp_expense_bulk_action(listview, action) {
	const names = listview.get_checked_items(true);
	if (!names.length) return;
	frappe.confirm(__("{0}: {1} selected expense(s)?", [__(frappe.utils.to_title_case(action.replace(/_/g, " "))), names.length]), () => {
		frappe
			.call({
				method: "techpark.techpark.doctype.tp_expense.tp_expense.bulk_action",
				args: { names, action },
				freeze: true,
			})
			.then((r) => {
				const { done, failed } = r.message;
				if (!failed.length) {
					frappe.show_alert({ message: __("{0} expense(s) updated.", [done]), indicator: "green" });
				} else {
					frappe.msgprint({
						title: __("{0} updated, {1} not updated", [done, failed.length]),
						message: failed.map((line) => frappe.utils.escape_html(line)).join("<br>"),
						indicator: "orange",
					});
				}
				listview.clear_checked_items();
				listview.refresh();
			});
	});
}
