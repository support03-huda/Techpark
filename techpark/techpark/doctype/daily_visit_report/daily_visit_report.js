// Copyright (c) 2026, Techpark International
// Customer Visit (DVR): plant/contact/segment pickers scoped to the customer,
// principal-wise rows (product categories scoped to the row's principal) with a Development and a
// Sales stage, a live progress bar per principal, and Expense / Follow-up cards for the visit.

frappe.provide("techpark.dvr");

// Keep in sync with DEVELOPMENT_PROGRESS / SALES_PROGRESS in daily_visit_report.py
techpark.dvr.STAGE_PROGRESS = {
	Introduction: 5,
	"Enquiry Received": 10,
	"Sent to Principal": 15,
	"Offer Received": 20,
	"Offer Submitted": 25,
	"Trial PO Received": 30,
	"Sample Received": 35,
	"Trial in Progress": 40,
	Retest: 40,
	"Successful Trial": 50,
	"Trial Failed": 40,
	"Bulk Trial PO": 75,
	Regularization: 100,
	"On Hold": 50,
	Cancelled: 50,
};
techpark.dvr.TRIAL_DONE = "Successful Trial";

frappe.ui.form.on("Daily Visit Report", {
	setup(frm) {
		frm.set_query("segment_application", () => ({ filters: { customer: frm.doc.customer || "" } }));
		frm.set_query("contact", () => ({
			filters: { customer: frm.doc.customer || "", is_active: 1 },
		}));
		frm.set_query("principal", "principals", () => ({ filters: { is_active: 1 } }));
		frm.set_query("supplier_product_category", "principals", (doc, cdt, cdn) => ({
			filters: { principal: locals[cdt][cdn].principal || "", is_active: 1 },
		}));
	},

	onload(frm) {
		if (frm.is_new() && frm.doc.customer) techpark.dvr.load_contacts(frm);
		// "New Visit" from an opportunity: start with its application line
		if (frm.is_new() && techpark.new_visit_row) {
			const values = techpark.new_visit_row;
			techpark.new_visit_row = null;
			frm.clear_table("principals");
			const row = frm.add_child("principals", values);
			frm.refresh_field("principals");
			techpark.dvr.check_development(frm, row);
		} else if (frm.is_new() && frm.doc.customer) {
			techpark.dvr.ask_open_lines(frm);
		}
	},

	refresh(frm) {
		// Only managers and admins may file a visit for someone else.
		const is_manager = ["Sales Manager", "TechPark Approver", "System Manager"].some((r) => frappe.user.has_role(r));
		frm.set_df_property("visited_by", "read_only", is_manager ? 0 : 1);
		techpark.show_lock(frm);
		frm.toggle_display("stage_completed", false);
		techpark.dvr.render_stage(frm);
		if (!frm.is_new()) techpark.dvr.render_actions(frm);
		if (frm.doc.docstatus < 2 && !frm.is_new()) {
			frm.add_custom_button(__("Expense"), () => techpark.dvr.new_expense(frm), __("Create"));
		}

		if (frm.doc.customer) {
			frm.add_custom_button(__("Open Customer"), () => frappe.set_route("Form", "TP Customer", frm.doc.customer));
		}
	},

	customer(frm) {
		// The (hidden) plant is set to the customer's on save.
		frm.set_value("plant", "");
		frm.set_value("contact", "");
		frm.set_value("segment_application", "");
		// Whether the trial is already done depends on the customer.
		(frm.doc.principals || []).forEach((row) => techpark.dvr.check_development(frm, row));
		if (!frm.doc.customer) return;
		techpark.dvr.load_contacts(frm);
		techpark.dvr.ask_open_lines(frm);
	},

	principals_remove(frm) {
		techpark.dvr.render_stage(frm);
	},
});

frappe.ui.form.on("DVR Principal", {
	principal(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "supplier_product_category", "");
		techpark.dvr.check_development(frm, locals[cdt][cdn]);
	},

	supplier_product_category(frm, cdt, cdn) {
		techpark.dvr.check_development(frm, locals[cdt][cdn]);
	},

	// Each row is one application line: its trial history is per line and spec.
	application(frm, cdt, cdn) {
		techpark.dvr.check_development(frm, locals[cdt][cdn]);
	},

	spec(frm, cdt, cdn) {
		techpark.dvr.check_development(frm, locals[cdt][cdn]);
	},

	development_status(frm, cdt, cdn) {
		techpark.dvr.update_row(frm, locals[cdt][cdn]);
	},

	sales_status(frm, cdt, cdn) {
		techpark.dvr.update_row(frm, locals[cdt][cdn]);
	},
});

// Was the trial for this customer + application line + principal + category + spec already successful
// on an earlier visit?
// Then the row starts in the Sales stage.
techpark.dvr.check_development = async function (frm, row) {
	if (!row.principal || frm.doc.docstatus !== 0) return;
	const done = await frappe.xcall("techpark.techpark.doctype.daily_visit_report.daily_visit_report.development_done", {
		customer: frm.doc.customer,
		principal: row.principal,
		supplier_product_category: row.supplier_product_category || "",
		exclude: frm.is_new() ? "" : frm.doc.name,
		application: row.application || "",
		spec: row.spec || "",
	});
	await frappe.model.set_value(row.doctype, row.name, "development_done_before", done ? 1 : 0);
	if (done) await frappe.model.set_value(row.doctype, row.name, "development_status", techpark.dvr.TRIAL_DONE);
	techpark.dvr.update_row(frm, row);
};

// Stage and progress of a row; the Sales Status only counts once the trial is successful.
techpark.dvr.update_row = function (frm, row) {
	const stage = row.development_status === techpark.dvr.TRIAL_DONE ? "Sales" : "Development";
	if (stage !== "Sales" && row.sales_status) {
		frappe.model.set_value(row.doctype, row.name, "sales_status", "");
	}
	if (row.stage !== stage) frappe.model.set_value(row.doctype, row.name, "stage", stage);
	const pct = techpark.dvr.STAGE_PROGRESS[(stage === "Sales" && row.sales_status) || row.development_status] || 0;
	if (row.progress !== pct) frappe.model.set_value(row.doctype, row.name, "progress", pct);
	techpark.dvr.render_stage(frm);
};

// A new visit for a customer with application lines still in progress (open opportunities): ask whether
// this visit continues them (their rows are added at their current status) or is a new application line.
techpark.dvr.ask_open_lines = async function (frm) {
	const customer = frm.doc.customer;
	if (!frm.is_new() || !customer || frm.doc.docstatus !== 0) return;
	const lines = await frappe.db.get_list("TP Opportunity", {
		filters: { customer, lead_status: ["in", ["Open", "On Hold"]], visits: [">", 0] },
		fields: ["application", "principal", "supplier_product_category", "spec", "size", "stage", "status", "last_visit", "next_action"],
		order_by: "last_visit desc",
		limit: 50,
	});
	// The customer may have been changed again while this was loading.
	if (!lines.length || frm.doc.customer !== customer) return;
	const esc = frappe.utils.escape_html;
	const fields = [
		{
			fieldtype: "HTML",
			options: `<p>${__("{0} already has these application lines in progress. Tick the ones this visit continues, or choose <b>New Application Line</b>.", [
				`<b>${esc(frm.doc.customer_name || customer)}</b>`,
			])}</p>`,
		},
	];
	lines.forEach((l, i) => {
		fields.push({
			fieldtype: "Check",
			fieldname: `line_${i}`,
			label: [l.application, l.principal, l.spec].filter(Boolean).join(" · ") + (l.status ? ` — ${__(l.status)}` : ""),
			description: [
				l.last_visit ? __("Last visit {0}", [frappe.datetime.str_to_user(l.last_visit)]) : "",
				l.next_action ? __("Next: {0}", [l.next_action]) : "",
			]
				.filter(Boolean)
				.join(" · "),
		});
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Continue an Application Line?"),
		fields,
		primary_action_label: __("Continue Selected"),
		primary_action(values) {
			const picked = lines.filter((l, i) => values[`line_${i}`]);
			if (!picked.length) {
				frappe.msgprint(__("Tick at least one line, or choose New Application Line."));
				return;
			}
			dialog.hide();
			techpark.dvr.continue_lines(frm, picked);
		},
		secondary_action_label: __("New Application Line"),
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.show();
};

// Rows for the chosen lines, starting at their current status; the user moves them on from there.
techpark.dvr.continue_lines = function (frm, lines) {
	(frm.doc.principals || []).filter((r) => !r.principal).forEach((r) => frappe.model.clear_doc(r.doctype, r.name));
	for (const l of lines) {
		const sales = l.stage === "Sales";
		const row = frm.add_child("principals", {
			application: l.application,
			principal: l.principal,
			supplier_product_category: l.supplier_product_category,
			spec: l.spec,
			size: l.size,
			development_status: sales ? techpark.dvr.TRIAL_DONE : l.status,
			sales_status: sales ? l.status : "",
		});
		techpark.dvr.check_development(frm, row);
	}
	frm.refresh_field("principals");
};

// A new visit starts with the customer's primary contact.
techpark.dvr.load_contacts = async function (frm) {
	if (frm.doc.contact || frm.doc.docstatus !== 0) return;
	const primary = await frappe.db.get_list("Customer Contact", {
		filters: { customer: frm.doc.customer, is_active: 1, is_primary: 1 },
		fields: ["name"],
		limit: 1,
	});
	if (primary.length) frm.set_value("contact", primary[0].name);
};

// One progress bar per principal: Development fills the first half, Sales the second.
techpark.dvr.render_stage = function (frm) {
	const esc = frappe.utils.escape_html;
	const rows = (frm.doc.principals || []).filter((row) => row.principal);
	techpark.dvr.render_headline(frm, rows);
	if (!rows.length) {
		frm.fields_dict.stage_html.$wrapper.html(
			`<div class="text-muted small">${__("Add the principals discussed to track their Development and Sales stage.")}</div>`
		);
		return;
	}
	const color = (status) =>
		["Bulk Trial PO", "Regularization"].includes(status) ? "var(--green-500)"
		: ["Cancelled", "Trial Failed"].includes(status) ? "var(--red-500)"
		: status === "On Hold" ? "var(--gray-500)"
		: "var(--blue-500)";
	const bars = rows
		.map((row) => {
			const status = (row.stage === "Sales" && row.sales_status) || row.development_status || "";
			const pct = row.progress || 0;
			const label = [row.application, row.principal, row.category_name].filter(Boolean).map(esc).join(" · ");
			return `<div style="margin-bottom:10px;">
				<div style="display:flex; justify-content:space-between; gap:8px; font-size:12px; margin-bottom:4px;">
					<span><b>${label}</b></span>
					<span>${techpark.dvr.stage_pill(row.stage)} <span class="text-muted">${status ? esc(__(status)) + " · " : ""}${pct}%</span></span>
				</div>
				<div style="position:relative; height:8px; border-radius:4px; background:var(--gray-200); overflow:hidden;">
					<div style="height:100%; width:${pct}%; background:${color(status)}; transition:width .3s;"></div>
					<div style="position:absolute; top:0; bottom:0; left:50%; width:2px; background:var(--fg-color);"></div>
				</div>
			</div>`;
		})
		.join("");
	frm.fields_dict.stage_html.$wrapper.html(`
		<div style="margin: 2px 0 6px;">
			<div class="control-label" style="margin-bottom:8px;">${__("Development")} → ${__("Sales")}</div>
			${bars}
		</div>`);
};

// Keep in sync with dvr_stage() in daily_visit_report.py and the list view.
techpark.dvr.STAGE_COLORS = { Development: "orange", Sales: "blue", "Development + Sales": "yellow" };

techpark.dvr.stage_pill = function (stage) {
	stage = stage || "Development";
	return `<span class="indicator-pill ${techpark.dvr.STAGE_COLORS[stage]}">${frappe.utils.escape_html(__(stage + " Stage"))}</span>`;
};

// Banner at the top of the form: which stage this visit is at, and each principal's stage.
techpark.dvr.render_headline = function (frm, rows) {
	// Own block in the form's message area, so other messages (e.g. the lock notice) stay.
	const $area = frm.layout.message;
	$area.find(".tp-stage-banner").remove();
	if (!$area.children().length) $area.addClass("hidden");
	if (!rows.length) return;
	const esc = frappe.utils.escape_html;
	const stages = new Set(rows.map((row) => row.stage || "Development"));
	const stage = stages.size > 1 ? "Development + Sales" : [...stages][0];
	const principals = rows
		.map((row) => {
			const label = [row.application, row.principal, row.category_name].filter(Boolean).map(esc).join(" · ");
			const status = (row.stage === "Sales" && row.sales_status) || row.development_status || "";
			return `<span style="margin-right:12px; white-space:nowrap;">${techpark.dvr.stage_pill(row.stage)} <b>${label}</b>${status ? ": " + esc(__(status)) : ""}</span>`;
		})
		.join("");
	$(`<div class="form-message border-bottom tp-stage-banner ${techpark.dvr.STAGE_COLORS[stage]}">
		<div style="display:flex; flex-wrap:wrap; align-items:center; gap:6px;">
			<span style="font-size:14px; font-weight:700; margin-right:12px;">${esc(__(stage + " Stage").toUpperCase())}</span>
			${principals}
		</div>
	</div>`).prependTo($area);
	$area.removeClass("hidden");
};

techpark.dvr.render_actions = async function (frm) {
	const wrapper = frm.fields_dict.actions_html.$wrapper;

	let follow = __("Set a Next Action to track it");
	if (frm.doc.follow_up) {
		const todo = await frappe.db.get_value("ToDo", frm.doc.follow_up, ["status", "date"]);
		const t = todo.message || {};
		follow = t.date ? __("{0} · due {1}", [t.status, frappe.datetime.str_to_user(t.date)]) : t.status;
	} else if (frm.doc.next_action) {
		follow = frm.doc.docstatus === 1 ? __("No follow-up created") : __("Created when the DVR is submitted");
	}

	const spent = (await frappe.xcall("techpark.techpark.doctype.tp_expense.tp_expense.get_visit_expenses", { visit: frm.doc.name })) || {};

	const card = (key, title, sub) => `
		<div class="tp-dvr-card" data-key="${key}" style="flex:1; min-width:180px; cursor:pointer; border:1px solid var(--border-color); border-radius:var(--border-radius-md); padding:10px 14px; background:var(--fg-color);">
			<div style="font-size:15px; font-weight:600;">${title}</div>
			<div class="text-muted small">${sub}</div>
		</div>`;

	wrapper.html(`<div style="display:flex; gap:12px; flex-wrap:wrap;">
		${card("expense", __("Expense"), spent.claims ? __("{0} claim(s) · {1}", [spent.claims, format_currency(spent.amount)]) : __("Add an expense for this visit"))}
		${card("followup", __("Follow-up"), frappe.utils.escape_html(follow))}
	</div>`);

	// Principal rows with their own Next Action get their own follow-up.
	const principal_follow_ups = (frm.doc.principals || []).filter((row) => row.follow_up).length;
	if (principal_follow_ups) {
		wrapper.find('[data-key="followup"] .text-muted').append(
			` · ${__("{0} principal follow-up(s)", [principal_follow_ups])}`
		);
	}

	wrapper.find(".tp-dvr-card").on("click", function () {
		const key = $(this).data("key");
		if (key === "expense") techpark.dvr.new_expense(frm);
		if (key !== "followup") return;
		if (principal_follow_ups) {
			frappe.set_route("List", "ToDo", { reference_type: frm.doctype, reference_name: frm.doc.name });
		} else if (frm.doc.follow_up) {
			frappe.set_route("Form", "ToDo", frm.doc.follow_up);
		}
	});
};

// A new expense claim with this visit as its first bill.
techpark.dvr.new_expense = function (frm) {
	frappe.model.with_doctype("TP Expense", () => {
		const expense = frappe.model.get_new_doc("TP Expense");
		expense.employee = frm.doc.visited_by;
		const bill = frappe.model.add_child(expense, "items");
		bill.expense_date = frm.doc.visit_date;
		bill.visit = frm.doc.name;
		bill.customer = frm.doc.customer;
		bill.customer_name = frm.doc.customer_name;
		frappe.set_route("Form", "TP Expense", expense.name);
	});
};
