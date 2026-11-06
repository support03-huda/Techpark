// Copyright (c) 2026, Techpark International
// Customer Visit (DVR): one application line per visit. The Stage (Development / Sales) is chosen
// first, then the line (principal, the customer's Technical Lead, category) and its status. On save the
// line is copied into the visit's hidden principal row (daily_visit_report.py), which opportunities,
// follow-ups and reports read. Plus a progress bar and Expense / Follow-up cards.

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
	"Bulk Trial PO": 70,
	"Enquiry Follow-up": 75,
	"Order Follow-up": 80,
	"Delivery Follow-up": 85,
	"Payment Follow-up": 90,
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
		frm.set_query("principal", () => ({ filters: { is_active: 1 } }));
		// Application = one of the customer's Technical Leads for the principal
		frm.set_query("technical_lead", () => {
			const filters = { customer: frm.doc.customer || "" };
			if (frm.doc.principal) filters.principal = frm.doc.principal;
			return { filters };
		});
		frm.set_query("supplier_product_category", () => ({
			filters: { principal: frm.doc.principal || "", is_active: 1 },
		}));
	},

	onload(frm) {
		if (frm.is_new() && frm.doc.customer) techpark.dvr.load_contacts(frm);
		// "New Visit" from an opportunity: start with its application line
		if (frm.is_new() && techpark.new_visit_row) {
			const values = techpark.new_visit_row;
			techpark.new_visit_row = null;
			if (values.stage) {
				frm._asked_lines = `${frm.doc.customer}|${values.stage}`; // this line is already picked
				frm.set_value("dvr_stage", values.stage);
			}
			techpark.dvr.continue_line(frm, values);
		} else if (frm.is_new() && techpark.dvr.same_principal) {
			// "+ Another Application": the visit details came in pre-filled; only the application is new
			techpark.dvr.same_principal = false;
			frm._asked_lines = `${frm.doc.customer}|${frm.doc.dvr_stage}`;
			frappe.show_alert({ message: __("Same visit and principal: pick the next Application."), indicator: "blue" });
		} else if (frm.is_new() && frm.doc.customer) {
			techpark.dvr.ask_open_lines(frm);
		}
	},

	refresh(frm) {
		// Only managers and admins may file a visit for someone else.
		const is_manager = ["Sales Manager", "TechPark Approver", "System Manager"].some((r) => frappe.user.has_role(r));
		frm.set_df_property("visited_by", "read_only", is_manager ? 0 : 1);
		techpark.show_lock(frm);
		techpark.dvr.set_new_lead_defaults(frm);
		techpark.dvr.setup_stage(frm);
		frm.toggle_display("stage_completed", false);
		techpark.dvr.render_stage(frm);
		if (!frm.is_new()) techpark.dvr.render_actions(frm);
		if (frm.doc.docstatus < 2 && !frm.is_new()) {
			frm.add_custom_button(__("Expense"), () => techpark.dvr.new_expense(frm), __("Create"));
		}

		if (frm.doc.customer) {
			frm.add_custom_button(__("Open Customer"), () => frappe.set_route("Form", "TP Customer", frm.doc.customer));
		}
		// One application per DVR: another application of the same principal on this visit is its own DVR
		if (frm.doc.docstatus < 2 && frm.doc.customer && frm.doc.principal) {
			frm.add_custom_button(__("+ Another Application (Same Principal)"), () => techpark.dvr.another_application(frm));
		}
	},

	customer(frm) {
		// The (hidden) plant is set to the customer's on save.
		frm.set_value("plant", "");
		frm.set_value("contact", "");
		frm.set_value("segment_application", "");
		// Whether the trial is already done depends on the customer.
		if (frm.doc.principal) techpark.dvr.check_development(frm, frm.doc);
		if (!frm.doc.customer) return;
		techpark.dvr.load_contacts(frm);
		techpark.dvr.ask_open_lines(frm);
	},

	principals_remove(frm) {
		techpark.dvr.render_stage(frm);
	},

	// Development or Sales: the rows show only that stage's status, and open lines of that stage are offered
	dvr_stage(frm) {
		if (frm.doc.principal) techpark.dvr.update_row(frm, frm.doc);
		techpark.dvr.ask_open_lines(frm);
	},

	validate(frm) {
		const d = frm.doc;
		if (!d.dvr_stage) frappe.throw(__("Select the Stage of this visit: Development or Sales."));
		if (!d.principal) frappe.throw(__("Select the Principal."));
		if (d.dvr_stage === "Sales" && !d.sales_status) frappe.throw(__("Select the Sales Status."));
		if (d.dvr_stage === "Development" && !d.development_status) frappe.throw(__("Select the Development Status."));
	},
});

// The visit's Stage is chosen first (Development or Sales); older visits may say "Development + Sales".
techpark.dvr.setup_stage = function (frm) {
	if (frm.doc.dvr_stage !== "Development + Sales") {
		frm.set_df_property("dvr_stage", "options", ["", "Development", "Sales"]);
	}
	frm.toggle_reqd("dvr_stage", frm.doc.docstatus === 0);
	// Which line this visit is about is fixed on submit; only its status moves on.
	for (const field of ["principal", "technical_lead", "application", "supplier_product_category", "spec", "size"]) {
		frm.set_df_property(field, "read_only", frm.doc.docstatus === 1 ? 1 : 0);
	}
};



// The visit's application line
frappe.ui.form.on("Daily Visit Report", {
	principal(frm) {
		if (techpark.dvr.filling_from_lead) return;
		frm.set_value("supplier_product_category", "");
		if (frm.doc.technical_lead) frm.set_value("technical_lead", "");
		techpark.dvr.check_development(frm, frm.doc);
	},

	// Picking a Technical Lead fills the line from it
	technical_lead(frm) {
		techpark.dvr.fill_from_lead(frm, frm.doc);
	},

	supplier_product_category(frm) {
		if (techpark.dvr.filling_from_lead) return;
		techpark.dvr.check_development(frm, frm.doc);
	},

	// Its trial history is per application line and spec.
	application(frm) {
		if (techpark.dvr.filling_from_lead) return;
		techpark.dvr.check_development(frm, frm.doc);
	},

	spec(frm) {
		techpark.dvr.check_development(frm, frm.doc);
	},

	development_status(frm) {
		techpark.dvr.update_row(frm, frm.doc);
	},

	sales_status(frm) {
		techpark.dvr.update_row(frm, frm.doc);
	},
});

// Copy a Technical Lead into the visit: principal, application, category and wheel size.
// "Create a new TP Technical Lead" opens the full Technical Lead form pre-filled; after
// saving it Frappe returns to this visit and sets the new lead. The link control reads
// this from the visit's own copy of the field, so it is set on every refresh (the name changes on save).
techpark.dvr.set_new_lead_defaults = function (frm) {
	const df = frappe.meta.get_docfield("Daily Visit Report", "technical_lead", frm.doc.name);
	if (!df) return;
	df.get_route_options_for_new_doc = (field) => ({
		customer: frm.doc.customer || "",
		principal: frm.doc.principal || "",
		application: (field.get_input_value && field.get_input_value()) || frm.doc.application || "",
	});
};

techpark.dvr.fill_from_lead = async function (frm, row) {
	if (!row.technical_lead) return;
	const lead = await frappe.db.get_value("TP Technical Lead", row.technical_lead, [
		"customer", "principal", "application", "supplier_product_category", "size_od", "size_t", "size_id",
	]).then((r) => r.message || {});
	if (lead.customer && frm.doc.customer && lead.customer !== frm.doc.customer) {
		frappe.msgprint(__("This Technical Lead belongs to another customer."));
		return frappe.model.set_value(row.doctype, row.name, "technical_lead", "");
	}
	const size = [lead.size_od, lead.size_t, lead.size_id].filter(Boolean).join(" x ");
	techpark.dvr.filling_from_lead = true;
	try {
		if (lead.principal && row.principal !== lead.principal) {
			await frappe.model.set_value(row.doctype, row.name, "principal", lead.principal);
		}
		await frappe.model.set_value(row.doctype, row.name, {
			application: lead.application || "",
			supplier_product_category: lead.supplier_product_category || "",
			...(size ? { size } : {}),
		});
	} finally {
		techpark.dvr.filling_from_lead = false;
	}
	techpark.dvr.check_development(frm, row);
};

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
	const visit_stage = frm.doc.dvr_stage;
	if (visit_stage === "Sales" && row.development_status !== techpark.dvr.TRIAL_DONE) {
		// A Sales visit follows lines whose development is complete
		frappe.model.set_value(row.doctype, row.name, "development_status", techpark.dvr.TRIAL_DONE);
		return; // the development_status trigger runs this again
	}
	if (visit_stage === "Development" && row.development_done_before) {
		frappe.show_alert({
			message: __("{0} already had a Successful Trial: record it on a Sales visit.", [row.application || row.principal]),
			indicator: "orange",
		});
	}
	const stage = row.development_status === techpark.dvr.TRIAL_DONE ? "Sales" : "Development";
	if (stage !== "Sales" && row.sales_status) {
		frappe.model.set_value(row.doctype, row.name, "sales_status", "");
	}
	if (row === frm.doc) return techpark.dvr.render_stage(frm);
	if (row.stage !== stage) frappe.model.set_value(row.doctype, row.name, "stage", stage);
	const pct = techpark.dvr.STAGE_PROGRESS[(stage === "Sales" && row.sales_status) || row.development_status] || 0;
	if (row.progress !== pct) frappe.model.set_value(row.doctype, row.name, "progress", pct);
	techpark.dvr.render_stage(frm);
};

// A new visit for a customer with application lines still in progress (open opportunities): ask whether
// this visit continues them (their rows are added at their current status) or is a new application line.
techpark.dvr.ask_open_lines = async function (frm) {
	const customer = frm.doc.customer;
	const stage = frm.doc.dvr_stage;
	if (!frm.is_new() || !customer || !stage || frm.doc.docstatus !== 0) return;
	// Ask once per customer + stage
	if (frm._asked_lines === `${customer}|${stage}`) return;
	frm._asked_lines = `${customer}|${stage}`;
	const lines = await frappe.db.get_list("TP Opportunity", {
		filters: { customer, stage, lead_status: ["in", ["Open", "On Hold"]], visits: [">", 0] },
		fields: ["application", "principal", "supplier_product_category", "spec", "size", "stage", "status", "last_visit", "next_action"],
		order_by: "last_visit desc",
		limit: 50,
	});
	// The customer or stage may have been changed again while this was loading.
	if (!lines.length || frm.doc.customer !== customer || frm.doc.dvr_stage !== stage) return;
	const esc = frappe.utils.escape_html;
	const fields = [
		{
			fieldtype: "HTML",
			options: `<p>${__("{0} already has these application lines in progress. Pick the one this visit continues, or choose <b>New Application Line</b>.", [
				`<b>${esc(frm.doc.customer_name || customer)}</b>`,
			])}</p>`,
		},
	];
	const label = (l) =>
		[l.application, l.principal, l.spec].filter(Boolean).join(" · ") +
		(l.status ? ` — ${__(l.status)}` : "") +
		(l.last_visit ? ` (${__("last visit {0}", [frappe.datetime.str_to_user(l.last_visit)])})` : "");
	fields.push({ fieldtype: "Select", fieldname: "line", label: __("Application Line"), options: lines.map(label), reqd: 1 });
	const dialog = new frappe.ui.Dialog({
		title: __("Continue an Application Line?"),
		fields,
		primary_action_label: __("Continue"),
		primary_action(values) {
			const picked = lines.find((l) => label(l) === values.line);
			if (!picked) return;
			dialog.hide();
			techpark.dvr.continue_line(frm, picked);
		},
		secondary_action_label: __("New Application Line"),
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.show();
};

// A new DVR for the same visit (customer, date, type, stage, employee) and principal; only the
// application (and its status) is left to fill. An unsaved visit is saved first.
techpark.dvr.another_application = async function (frm) {
	if (frm.is_new() || frm.is_dirty()) {
		await frm.save();
		if (frm.is_new() || frm.is_dirty()) return; // the save failed: its message is already shown
	}
	const d = frm.doc;
	techpark.dvr.same_principal = true; // picked up in onload: don't ask about open lines
	frappe.new_doc("Daily Visit Report", {
		customer: d.customer,
		customer_name: d.customer_name,
		visit_date: d.visit_date,
		visit_time: d.visit_time,
		dvr_type: d.dvr_type,
		dvr_stage: d.dvr_stage,
		visited_by: d.visited_by,
		principal: d.principal,
	});
};

// The visit continues this line at its current status; the user moves it on from there.
techpark.dvr.continue_line = async function (frm, l) {
	const sales = l.stage === "Sales" || frm.doc.dvr_stage === "Sales";
	techpark.dvr.filling_from_lead = true;
	try {
		await frm.set_value({
			principal: l.principal || "",
			technical_lead: "",
			application: l.application || "",
			supplier_product_category: l.supplier_product_category || "",
			spec: l.spec || "",
			size: l.size || "",
		});
		// The line's Technical Lead, if it has one
		const leads = await frappe.db.get_list("TP Technical Lead", {
			filters: { customer: frm.doc.customer, principal: l.principal || "", application: l.application || "" },
			limit: 1,
		});
		if (leads.length) await frm.set_value("technical_lead", leads[0].name);
		const status = l.status || "";
		await frm.set_value({
			development_status: sales ? techpark.dvr.TRIAL_DONE : status,
			sales_status: sales && l.stage === "Sales" ? status : "",
		});
	} finally {
		techpark.dvr.filling_from_lead = false;
	}
	techpark.dvr.check_development(frm, frm.doc);
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
// The visit's line(s) for the progress bar: older visits may have several rows.
techpark.dvr.lines = function (frm) {
	const rows = (frm.doc.principals || []).filter((row) => row.principal);
	if (rows.length > 1) return rows;
	const d = frm.doc;
	if (!d.principal) return [];
	const stage = d.development_status === techpark.dvr.TRIAL_DONE ? "Sales" : "Development";
	return [{
		application: d.application,
		principal: d.principal,
		category_name: (rows[0] && rows[0].category_name) || "",
		stage,
		development_status: d.development_status,
		sales_status: d.sales_status,
		progress: techpark.dvr.STAGE_PROGRESS[(stage === "Sales" && d.sales_status) || d.development_status] || 0,
	}];
};

techpark.dvr.render_stage = function (frm) {
	const esc = frappe.utils.escape_html;
	const rows = techpark.dvr.lines(frm);
	techpark.dvr.render_headline(frm, rows);
	if (!rows.length) {
		frm.fields_dict.stage_html.$wrapper.html(
			`<div class="text-muted small">${__("Pick the principal and application to track its Development and Sales stage.")}</div>`
		);
		return;
	}
	const color = (status) =>
		["Bulk Trial PO", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up", "Regularization"].includes(status) ? "var(--green-500)"
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
