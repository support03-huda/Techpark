// Copyright (c) 2026, Techpark International
// Expense Approvals page for managers and approvers: the team's expenses waiting for their approval,
// with every bill and its attachments, Approve / Reject per expense and Approve Selected; and the team's
// history. The user's own expenses are on My Expenses (the expense list), not here.

// Server method of the page.
const TP_APPROVALS_METHOD = "techpark.techpark.doctype.tp_expense.tp_expense.get_approvals";
// Colour per status, as in the expense list.
const TP_APPROVAL_COLORS = { Draft: "gray", "Pending Manager": "orange", "Pending Admin": "blue", Approved: "green" };

// Look of the page; the colours also work in dark mode.
const TP_APPROVALS_STYLE = `
	.tp-approvals { max-width: 1100px; margin: 0 auto; padding: 16px 0; }
	.tp-approvals .tp-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); }
	.tp-approvals .tp-tab { padding: 8px 16px; cursor: pointer; color: var(--text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
	.tp-approvals .tp-tab.tp-active { color: var(--text-color); font-weight: 600; border-bottom-color: var(--primary); }
	.tp-approvals .tp-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
	.tp-approvals .tp-card { border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }
	.tp-approvals .tp-card-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
	.tp-approvals .tp-card-title { font-weight: 600; }
	.tp-approvals .tp-card-amount { margin-left: auto; text-align: right; }
	.tp-approvals .tp-card-amount b { font-size: 16px; }
	.tp-approvals .tp-card-note { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
	.tp-approvals .tp-card-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
	.tp-approvals .tp-table-wrap { overflow-x: auto; margin-top: 10px; }
	.tp-approvals table { font-size: 13px; margin-bottom: 0; }
	.tp-approvals td.tp-number, .tp-approvals th.tp-number { text-align: right; white-space: nowrap; }
	.tp-approvals .tp-empty { padding: 48px 16px; text-align: center; color: var(--text-muted); }
`;

// Frappe calls this once, when the page is first opened.
frappe.pages["tp-expense-approvals"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Expense Approvals"), single_column: true });
	$(`<style>${TP_APPROVALS_STYLE}</style>`).appendTo(page.main);
	wrapper.tp_approvals = new TPExpenseApprovals(page);
};

// Frappe calls this every time the page is shown; load fresh figures (an expense may have been approved meanwhile).
frappe.pages["tp-expense-approvals"].on_page_show = function (wrapper) {
	wrapper.tp_approvals && wrapper.tp_approvals.load();
};

// The page: two tabs, a list of expense cards, and the approval buttons.
class TPExpenseApprovals {
	constructor(page) {
		this.page = page;
		this.view = "pending";
		this.$body = $(`<div class="tp-approvals"></div>`).appendTo(page.main);
		page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
	}

	load() {
		this.$body.html(`<div class="tp-empty">${__("Loading...")}</div>`);
		frappe.call(TP_APPROVALS_METHOD, { view: this.view }).then((r) => this.render(r.message));
	}

	render(data) {
		this.expenses = data.expenses || [];
		this.$body.empty();
		if (!data.is_approver) {
			this.$body.html(
				`<div class="tp-empty">${__("Nobody reports to you (TP Team Member), so there are no expenses for you to approve.")}<br>
				<a href="/desk/tp-expense">${__("Go to My Expenses")}</a></div>`
			);
			return;
		}
		this.render_tabs();
		this.render_bar();
		if (!this.expenses.length) {
			this.$body.append(
				`<div class="tp-empty">${
					this.view === "pending" ? __("Nothing is waiting for your approval.") : __("Your team has not sent any expenses yet.")
				}</div>`
			);
			return;
		}
		this.expenses.forEach((expense) => this.$body.append(this.card(expense)));
	}

	render_tabs() {
		const $tabs = $(`<div class="tp-tabs"></div>`).appendTo(this.$body);
		[
			["pending", __("Waiting for My Approval")],
			["history", __("Team History")],
		].forEach(([view, label]) => {
			$(`<div class="tp-tab ${view === this.view ? "tp-active" : ""}">${label}</div>`)
				.appendTo($tabs)
				.on("click", () => {
					this.view = view;
					this.load();
				});
		});
	}

	render_bar() {
		const total = this.expenses.reduce((sum, expense) => sum + flt(expense.total_amount), 0);
		const $bar = $(`<div class="tp-bar">
			<div class="text-muted">${__("{0} expense(s), {1}", [this.expenses.length, format_currency(total)])}</div>
		</div>`).appendTo(this.$body);
		if (this.view !== "pending" || !this.expenses.length) return;
		$(`<button class="btn btn-primary btn-sm">${__("Approve Selected")}</button>`)
			.appendTo($bar)
			.on("click", () => this.approve_selected());
	}

	card(expense) {
		const esc = frappe.utils.escape_html;
		const tick = this.view === "pending" ? `<input type="checkbox" class="tp-tick" data-name="${esc(expense.name)}">` : "";
		const manager_note = expense.approved_by
			? `<div class="tp-card-note">${__("Manager approved by {0} on {1}", [esc(expense.approved_by_name || expense.approved_by), frappe.datetime.str_to_user(expense.approved_on)])}</div>`
			: "";
		const remark = expense.remark ? `<div class="tp-card-note">${__("Remark")}: ${esc(expense.remark)}</div>` : "";
		const $card = $(`<div class="tp-card">
			<div class="tp-card-head">
				${tick}
				<a class="tp-card-title" href="/desk/tp-expense/${encodeURIComponent(expense.name)}">${esc(expense.name)}</a>
				<span>${esc(expense.employee_name || expense.employee)}</span>
				<span class="text-muted">${frappe.datetime.str_to_user(expense.entry_date)}</span>
				<span class="indicator-pill ${TP_APPROVAL_COLORS[expense.status] || "gray"}">${__(expense.status)}</span>
				<span class="tp-card-amount"><b>${format_currency(expense.total_amount)}</b>
					${flt(expense.passed_amount) !== flt(expense.total_amount) ? `<div class="tp-card-note">${__("Passed")}: ${format_currency(expense.passed_amount)}</div>` : ""}
				</span>
			</div>
			${remark}${manager_note}
			<div class="tp-table-wrap">${this.bills_table(expense.bills || [])}</div>
			<div class="tp-card-actions"></div>
		</div>`);
		const $actions = $card.find(".tp-card-actions");
		if (expense.actions.includes("approve")) {
			const question =
				expense.status === "Pending Manager"
					? __("Approve expense {0} of {1} and send it to the approver?", [expense.name, esc(expense.employee_name)])
					: __("Give the final approval to expense {0} for {1}?", [expense.name, format_currency(expense.passed_amount)]);
			$(`<button class="btn btn-success btn-sm">${__("Approve")}</button>`)
				.appendTo($actions)
				.on("click", () => frappe.confirm(question, () => this.run(expense.name, "approve")));
		}
		if (expense.actions.includes("reject")) {
			$(`<button class="btn btn-danger btn-sm">${__("Reject")}</button>`)
				.appendTo($actions)
				.on("click", () => this.reject(expense.name));
		}
		$(`<a class="btn btn-default btn-sm" href="/desk/tp-expense/${encodeURIComponent(expense.name)}">${__("Open")}</a>`).appendTo($actions);
		return $card;
	}

	bills_table(bills) {
		const esc = frappe.utils.escape_html;
		const file = (url, label) => (url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${label}</a>` : "");
		const rows = bills
			.map(
				(bill) => `<tr>
					<td>${bill.idx}</td>
					<td>${frappe.datetime.str_to_user(bill.expense_date)}</td>
					<td>${esc(bill.expense_type || "")}</td>
					<td>${esc(bill.customer_name || "")}${bill.visit ? `<div class="text-muted small">${__("Visit")} ${esc(bill.visit)}</div>` : ""}</td>
					<td>${esc(bill.bill_no || "")}</td>
					<td>${esc(bill.description || "")}</td>
					<td>${[file(bill.bill, __("Bill")), file(bill.other_attachment, __("Other"))].filter(Boolean).join(" · ") || "-"}</td>
					<td class="tp-number">${format_currency(bill.amount)}</td>
				</tr>`
			)
			.join("");
		return `<table class="table table-bordered">
			<thead><tr>
				<th>#</th><th>${__("Date")}</th><th>${__("Expense Type")}</th><th>${__("Customer")}</th>
				<th>${__("Bill No")}</th><th>${__("Description")}</th><th>${__("Attachments")}</th><th class="tp-number">${__("Amount")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	}

	run(name, method, args) {
		return frappe
			.call({ method: "run_doc_method", args: { dt: "TP Expense", dn: name, method, args: JSON.stringify(args || {}) }, freeze: true })
			.then(() => {
				frappe.show_alert({ message: __("Expense {0} updated.", [name]), indicator: "green" });
				this.load();
			});
	}

	reject(name) {
		frappe.prompt(
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
			(values) => this.run(name, "reject", { reason: values.reason }),
			__("Reject Expense {0}", [name]),
			__("Reject")
		);
	}

	approve_selected() {
		const names = this.$body.find(".tp-tick:checked").map((i, el) => $(el).data("name")).get();
		if (!names.length) {
			frappe.show_alert({ message: __("Tick the expenses to approve first."), indicator: "orange" });
			return;
		}
		frappe.confirm(__("Approve {0} selected expense(s)?", [names.length]), () => {
			frappe
				.call({
					method: "techpark.techpark.doctype.tp_expense.tp_expense.bulk_action",
					args: { names, action: "approve" },
					freeze: true,
				})
				.then((r) => {
					const { done, failed } = r.message;
					failed.length
						? frappe.msgprint({ title: __("{0} approved, {1} not approved", [done, failed.length]), message: failed.map(frappe.utils.escape_html).join("<br>"), indicator: "orange" })
						: frappe.show_alert({ message: __("{0} expense(s) approved.", [done]), indicator: "green" });
					this.load();
				});
		});
	}
}
