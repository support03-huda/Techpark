// Copyright (c) 2026, Techpark International
// Customer Visit (DVR): plant/contact pickers scoped to the customer, a live
// stage-progress bar, and Expense / Follow-up cards for the visit.

frappe.provide("techpark.dvr");

// Keep in sync with STAGE_PROGRESS in daily_visit_report.py
techpark.dvr.STAGE_PROGRESS = {
	Introduction: 10,
	"Received Enquiry": 25,
	"Requirement Shared": 40,
	"Technical Discussion": 50,
	"Trial / Sample": 60,
	"Quotation Submitted": 75,
	Negotiation: 90,
	"Order Received": 100,
};

frappe.ui.form.on("Daily Visit Report", {
	setup(frm) {
		frm.set_query("plant", () => ({
			filters: { customer: frm.doc.customer || "", is_active: 1 },
		}));
	},

	onload(frm) {
		if (frm.doc.customer) techpark.dvr.load_contacts(frm);
	},

	refresh(frm) {
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

	async customer(frm) {
		frm.set_value("plant", "");
		frm.set_value("contact_person", "");
		if (!frm.doc.customer) return;
		techpark.dvr.load_contacts(frm);

		// Only one active plant? Pick it.
		const plants = await frappe.db.get_list("Plant", {
			filters: { customer: frm.doc.customer, is_active: 1 },
			fields: ["name"],
			limit: 2,
		});
		if (plants.length === 1) frm.set_value("plant", plants[0].name);
	},

	lead_status(frm) {
		if (frm.doc.lead_status === "Won") frm.set_value("lead_stage", "Order Received");
		techpark.dvr.update_progress(frm);
	},

	lead_stage(frm) {
		techpark.dvr.update_progress(frm);
	},
});

techpark.dvr.load_contacts = async function (frm) {
	const customer = await frappe.db.get_doc("TP Customer", frm.doc.customer);
	const options = (customer.contacts || []).map((c) =>
		c.designation ? `${c.name1} (${c.designation})` : c.name1
	);
	frm.set_df_property("contact_person", "options", options);
	const primary = (customer.contacts || []).find((c) => c.is_primary);
	if (primary && !frm.doc.contact_person && frm.doc.docstatus === 0) {
		frm.set_value("contact_person", primary.designation ? `${primary.name1} (${primary.designation})` : primary.name1);
	}
};

techpark.dvr.update_progress = function (frm) {
	const pct = frm.doc.lead_status === "Won" ? 100 : techpark.dvr.STAGE_PROGRESS[frm.doc.lead_stage] || 0;
	frm.set_value("stage_completed", pct);
	techpark.dvr.render_stage(frm);
};

techpark.dvr.render_stage = function (frm) {
	const pct = frm.doc.stage_completed || 0;
	const color = { Won: "var(--green-500)", Lost: "var(--red-500)", "On Hold": "var(--gray-500)" }[frm.doc.lead_status] || "var(--blue-500)";
	const note = frm.doc.lead_stage
		? __("{0}% of the lead stage completed ({1})", [pct, frm.doc.lead_status || ""])
		: __("Select a Lead Stage to track progress");
	frm.fields_dict.stage_html.$wrapper.html(`
		<div style="margin: 2px 0 6px;">
			<div class="control-label" style="margin-bottom:6px;">${__("Stage Completed")}</div>
			<div style="height:8px; border-radius:4px; background:var(--gray-200); overflow:hidden;">
				<div style="height:100%; width:${pct}%; background:${color}; transition:width .3s;"></div>
			</div>
			<div class="text-muted small" style="margin-top:4px;">${frappe.utils.escape_html(note)}</div>
		</div>`);
};

techpark.dvr.render_actions = async function (frm) {
	const wrapper = frm.fields_dict.actions_html.$wrapper;
	const expenses = await frappe.db.get_list("Visit Expense", {
		filters: { daily_visit_report: frm.doc.name },
		fields: ["amount"],
		limit: 0,
	});
	const spent = expenses.reduce((s, e) => s + (e.amount || 0), 0);

	let follow = __("Set a Next Action to track it");
	if (frm.doc.follow_up) {
		const todo = await frappe.db.get_value("ToDo", frm.doc.follow_up, ["status", "date"]);
		const t = todo.message || {};
		follow = t.date ? __("{0} · due {1}", [t.status, frappe.datetime.str_to_user(t.date)]) : t.status;
	} else if (frm.doc.next_action) {
		follow = frm.doc.docstatus === 1 ? __("No follow-up created") : __("Created when the DVR is submitted");
	}

	const card = (key, title, sub) => `
		<div class="tp-dvr-card" data-key="${key}" style="flex:1; min-width:180px; cursor:pointer; border:1px solid var(--border-color); border-radius:var(--border-radius-md); padding:10px 14px; background:var(--fg-color);">
			<div style="font-size:15px; font-weight:600;">${title}</div>
			<div class="text-muted small">${sub}</div>
		</div>`;

	wrapper.html(`<div style="display:flex; gap:12px; flex-wrap:wrap;">
		${card("expense", __("Expense"), expenses.length ? __("{0} claimed · {1}", [expenses.length, format_currency(spent)]) : __("Link expense to DVR"))}
		${card("followup", __("Follow-up"), frappe.utils.escape_html(follow))}
	</div>`);

	wrapper.find(".tp-dvr-card").on("click", function () {
		const key = $(this).data("key");
		if (key === "expense") techpark.dvr.new_expense(frm);
		if (key === "followup" && frm.doc.follow_up) frappe.set_route("Form", "ToDo", frm.doc.follow_up);
	});
};

techpark.dvr.new_expense = function (frm) {
	frappe.new_doc("Visit Expense", {
		daily_visit_report: frm.doc.name,
		expense_date: frm.doc.visit_date,
		employee: frm.doc.visited_by,
	});
};
