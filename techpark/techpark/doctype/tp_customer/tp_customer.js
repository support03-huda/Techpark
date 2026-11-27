// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// Plants / Products Info / Commercial / Technical Lead / Visits tabs: summary tiles
// above editable tables. These and the Contacts table are synced to the real records on
// save (techpark/customer_sync.py). The Products Info overview is a read-only summary of its table.

// 2026-11-26: a Save button on an opened table row (Technical Leads, Visits, Products ...): saves the customer
techpark.add_row_save = function (frm) {
	const row = frm.cur_grid;
	if (!row || !row.grid_form || !frm.perm[0]?.write) return;
	const $actions = row.grid_form.wrapper.find(".grid-header-toolbar .row-actions");
	if ($actions.find(".tp-row-save").length) return;
	$(`<button class="btn btn-primary btn-sm pull-right tp-row-save">${__("Save")}</button>`)
		.appendTo($actions)
		.on("click", (e) => {
			e.stopPropagation(); // the heading click would close the row
			row.toggle_view(false);
			frm.save();
		});
	techpark.add_row_freeze(frm, row, $actions);
};

// 2026-11-27: a frozen lead's row: every field read only (in the grid and the opened row), no Delete
techpark.LAYOUT_TYPES = ["Section Break", "Column Break", "Tab Break", "HTML", "Button"];
techpark.lock_frozen_row = function (frm, cdn) {
	const grid = frm.fields_dict.technical_leads && frm.fields_dict.technical_leads.grid;
	const d = locals["TP Customer Technical Lead"] && locals["TP Customer Technical Lead"][cdn];
	const gr = grid && grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
	if (!d || !d.is_frozen || !gr) return;
	for (const df of gr.docfields || []) {
		if (techpark.LAYOUT_TYPES.includes(df.fieldtype)) continue;
		df.read_only = 1; // this row's own copy of the fields
		gr.set_field_property(df.fieldname, "read_only", 1);
	}
	if (gr.grid_form) {
		gr.grid_form.wrapper.find(".grid-delete-row, .grid-insert-row, .grid-insert-row-below, .grid-duplicate-row, .grid-move-row").hide();
		if (!gr.grid_form.wrapper.find(".tp-frozen-note").length) {
			$(`<div class="tp-frozen-note alert alert-info" style="margin:8px 0">${__("Frozen: no changes until an admin presses Unfreeze.")}</div>`)
				.prependTo(gr.grid_form.wrapper.find(".grid-form-body"));
		}
	}
};
techpark.lock_frozen_rows = function (frm) {
	for (const d of frm.doc.technical_leads || []) if (d.is_frozen) techpark.lock_frozen_row(frm, d.name);
};

// 2026-11-27: Freeze / Unfreeze a saved Technical Lead from its row (admins); a frozen row is read only for others
techpark.add_row_freeze = function (frm, row, $actions) {
	const d = row.doc;
	if (d.doctype !== "TP Customer Technical Lead" || !d.record) return;
	// 2026-11-27: Freeze for whoever may edit, Unfreeze for admins only
	const o = frm.doc.__onload || {};
	if (!(d.is_frozen ? o.can_unfreeze : o.can_freeze) || $actions.find(".tp-row-freeze").length) return;
	$(`<button class="btn btn-default btn-sm pull-right tp-row-freeze">${d.is_frozen ? __("Unfreeze") : __("Freeze")}</button>`)
		.appendTo($actions)
		.on("click", (e) => {
			e.stopPropagation();
			const go = () =>
				frappe.xcall("techpark.techpark.doctype.tp_technical_lead.tp_technical_lead.set_frozen", { name: d.record, frozen: d.is_frozen ? 0 : 1 })
					.then(() => window.location.reload()); // 2026-11-27: read-only state set while frozen must go
			if (frm.is_dirty()) return frappe.msgprint(__("Save the customer first."));
			if (d.is_frozen) go();
			else frappe.confirm(__("Freeze {0}? Nobody can change it until an admin presses Unfreeze.", [frappe.utils.escape_html(d.record)]), go);
		});
};
if (!techpark.row_save_bound) {
	techpark.row_save_bound = true;
	frappe.model.with_doctype("TP Customer", () => {
		for (const df of frappe.get_meta("TP Customer").fields.filter((f) => f.fieldtype === "Table")) {
			frappe.ui.form.on(df.options, {
				form_render: (frm, cdt, cdn) => {
					techpark.add_row_save(frm);
					techpark.lock_frozen_row(frm, cdn); // 2026-11-27
				},
			});
		}
	});
}

frappe.ui.form.on("TP Customer", {
	setup(frm) {
		frm.set_query("territory_region", () => ({ filters: { is_active: 1 } }));
		// Principals is a Table MultiSelect (no grid): its query is set on the field itself
		frm.set_query("principals", () => ({ filters: { is_active: 1 } }));
		frm.set_query("principal", "visits", () => ({ filters: { is_active: 1 } }));
		// Only the selected principal's product categories
		frm.set_query("supplier_product_category", "visits", (doc, cdt, cdn) => ({
			filters: { principal: locals[cdt][cdn].principal || "", is_active: 1 },
		}));
		frm.set_query("principal", "technical_leads", () => ({ filters: { is_active: 1 } }));
		frm.set_query("supplier_product_category", "technical_leads", (doc, cdt, cdn) => ({
			filters: { principal: locals[cdt][cdn].principal || "", is_active: 1 },
		}));
	},

	refresh(frm) {
		const M = techpark.customer_master;
		// Only this customer's plants in the tables that point to a plant
		const plant_fields = {
			production: "plant",
			turnovers: "plant",
			visits: "plant",
		};
		for (const [table, field] of Object.entries(plant_fields)) {
			if (frm.fields_dict[table]) {
				frm.set_query(field, table, () => ({ filters: { customer: frm.doc.name || "" } }));
			}
		}
		M.set_contact_options(frm);
		M.render_plants(frm);
		if (frm.perm[0]?.write) {
			frm.add_custom_button(__("Scan Visiting Card"), () => M.upload_card(frm));
		}
		// 2026-11-26: the Technical Lead rows as saved (asked on save when a change reaches their visits)
		frm._lead_rows = {};
		if (techpark.lead_snapshot) {
			for (const r of frm.doc.technical_leads || []) if (r.record) frm._lead_rows[r.name] = techpark.lead_snapshot(r);
		}
		if (frm.is_new()) return;
		M.render_production(frm);
		M.render_commercial(frm);
		M.render_technical(frm);
		M.render_visits(frm);
		techpark.lock_frozen_rows(frm); // 2026-11-27: frozen leads' rows read only
		// "Customer Card" is the default print format of TP Customer
		frm.add_custom_button(__("Print Customer Card"), () => frm.print_doc());
	},
});

// Re-count the tiles as rows are added / edited / removed
frappe.ui.form.on("TP Customer Plant", {
	plants_add: (frm) => techpark.customer_master.render_plants(frm),
	plants_remove: (frm) => techpark.customer_master.render_plants(frm),
	is_active: (frm) => techpark.customer_master.render_plants(frm),
});
frappe.ui.form.on("TP Customer Production", {
	production_add: (frm) => techpark.customer_master.render_production(frm),
	production_remove: (frm) => techpark.customer_master.render_production(frm),
	product: (frm) => techpark.customer_master.render_production(frm),
	production_volume: (frm) => techpark.customer_master.render_production(frm),
	unit: (frm) => techpark.customer_master.render_production(frm),
	frequency: (frm) => techpark.customer_master.render_production(frm),
});
// 2026-11-26: "This will affect N visits. Do you want to submit?" for changed Technical Lead rows that have visits
frappe.ui.form.on("TP Customer", {
	async validate(frm) {
		if (!techpark.ask_lead_visits) return;
		const items = (frm.doc.technical_leads || [])
			.filter((r) => r.record && (frm._lead_rows || {})[r.name])
			.map((r) => ({ lead: r.record, saved: frm._lead_rows[r.name], row: r, doctype: "TP Customer Technical Lead" }));
		if (!(await techpark.ask_lead_visits(items))) frappe.validated = false;
	},
	abrasive_consumption_cr: (frm) => techpark.customer_master.render_production(frm),
	annual_turnover_cr: (frm) => techpark.customer_master.render_production(frm),
});
frappe.ui.form.on("TP Customer Technical Lead", {
	principal(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "supplier_product_category", "");
	},
	technical_leads_add: (frm) => techpark.customer_master.render_technical(frm),
	technical_leads_remove: (frm) => techpark.customer_master.render_technical(frm),
	application: (frm) => techpark.customer_master.render_technical(frm),
	grinding_process: (frm) => techpark.customer_master.render_technical(frm),
	supplier_product_category: (frm) => techpark.customer_master.render_technical(frm),
	annual_demand_amount: (frm) => techpark.customer_master.render_technical(frm),
	annual_quantity: (frm) => techpark.customer_master.render_technical(frm),
	// 2026-11-21: Principal share + up to 4 competitors
	principal_share: (frm) => techpark.customer_master.render_technical(frm),
	progress: (frm) => techpark.customer_master.render_technical(frm),
});
frappe.ui.form.on("TP Customer Turnover", {
	turnovers_add: (frm) => techpark.customer_master.render_commercial(frm),
	turnovers_remove: (frm) => techpark.customer_master.render_commercial(frm),
	amount: (frm) => techpark.customer_master.render_commercial(frm),
});
frappe.ui.form.on("TP Customer Visit", {
	visits_add(frm, cdt, cdn) {
		// Pre-fill the primary contact and, if there is only one, the plant
		const primary = (frm.doc.contacts || []).find((c) => c.is_primary && c.is_active);
		if (primary) frappe.model.set_value(cdt, cdn, "contact_person", techpark.customer_master.contact_label(primary));
		const active = (frm.doc.plants || []).filter((p) => p.is_active && p.record);
		if (active.length === 1) frappe.model.set_value(cdt, cdn, "plant", active[0].record);
		techpark.customer_master.render_visits(frm);
	},
	visits_remove: (frm) => techpark.customer_master.render_visits(frm),
	visit_date: (frm) => techpark.customer_master.render_visits(frm),
	lead_status(frm, cdt, cdn) {
		if (locals[cdt][cdn].lead_status === "Won") frappe.model.set_value(cdt, cdn, "lead_stage", "Bulk Trial PO");
		techpark.customer_master.render_visits(frm);
	},
	principal(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "supplier_product_category", "");
	},
});
frappe.ui.form.on("Company contacts", {
	person_name: (frm) => techpark.customer_master.set_contact_options(frm),
	designation: (frm) => techpark.customer_master.set_contact_options(frm),
	is_active: (frm) => techpark.customer_master.set_contact_options(frm),
	contacts_remove: (frm) => techpark.customer_master.set_contact_options(frm),
});

frappe.provide("techpark.customer_master");

techpark.customer_master.get_list = function (doctype, filters, fields) {
	return frappe
		.call({
			method: "frappe.client.get_list",
			args: { doctype, filters, fields, limit_page_length: 0 },
		})
		.then((r) => r.message || []);
};

techpark.customer_master.stats_html = function (stats) {
	const tiles = stats
		.map(
			(s) => `
			<div style="flex:1; min-width:140px; border:1px solid var(--border-color); border-radius:var(--border-radius); padding:12px 16px; background:var(--card-bg, var(--fg-color));">
				<div style="font-size:22px; font-weight:600; line-height:1.3;">${frappe.utils.escape_html(String(s.value))}</div>
				<div class="text-muted" style="font-size:12px; margin-top:2px;">${frappe.utils.escape_html(s.label)}</div>
			</div>`
		)
		.join("");
	return `<div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:8px;">${tiles}</div>`;
};

techpark.customer_master.table_html = function (headers, rows) {
	if (!rows.length) {
		return `<p class="text-muted" style="margin-bottom:16px;">No records yet.</p>`;
	}
	const head = headers.map((h) => `<th>${frappe.utils.escape_html(h)}</th>`).join("");
	const body = rows
		.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
		.join("");
	return `<div style="border:1px solid var(--border-color); border-radius:var(--border-radius); overflow:hidden; margin-bottom:16px;">
		<table class="table table-bordered" style="margin-bottom:0;">
			<thead><tr>${head}</tr></thead>
			<tbody>${body}</tbody>
		</table>
	</div>`;
};

techpark.customer_master.badge = function (text, color) {
	return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(text)}</span>`;
};

techpark.customer_master.wrap = function (html) {
	return `<div style="padding:16px 2px 4px;">${html}</div>`;
};

techpark.customer_master.link = function (doctype, name, label) {
	return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${frappe.utils.escape_html(label || name)}</a>`;
};


techpark.customer_master.render_plants = function (frm) {
	if (!frm.fields_dict.plants_html) return;
	const M = techpark.customer_master;
	const plants = frm.doc.plants || [];
	frm.fields_dict.plants_html.$wrapper.html(
		M.wrap(
			M.stats_html([
				{ label: "Total Plants", value: plants.length },
				{ label: "Active Plants", value: plants.filter((p) => p.is_active).length },
			])
		)
	);
};

// Products Info tab (Customer Card format): tiles for the company figures, then the products range
// grouped by category, each product with its production volume. Edited in the table below it.
techpark.customer_master.render_production = async function (frm) {
	if (!frm.fields_dict.production_html) return;
	const M = techpark.customer_master;
	const esc = frappe.utils.escape_html;
	const rows = (frm.doc.production || []).filter((r) => r.product);
	const wrapper = frm.fields_dict.production_html.$wrapper;
	const token = (M._production_token = (M._production_token || 0) + 1);

	const ids = (field) => [...new Set(rows.map((r) => r[field]).filter(Boolean))];
	const product_ids = ids("product");
	const products = product_ids.length
		? await M.get_list("Customer Product", { name: ["in", product_ids] }, ["name", "product_name", "product_category"])
		: [];
	const product_map = Object.fromEntries(products.map((p) => [String(p.name), p]));
	const category_ids = [...new Set(products.map((p) => p.product_category).filter(Boolean))];
	const categories = category_ids.length
		? await M.get_list("Product Category", { name: ["in", category_ids] }, ["name", "category_name"])
		: [];
	const category_map = Object.fromEntries(categories.map((c) => [String(c.name), c.category_name]));
	const unit_ids = ids("unit");
	const units = unit_ids.length ? await M.get_list("Unit", { name: ["in", unit_ids] }, ["name", "unit_name"]) : [];
	const unit_map = Object.fromEntries(units.map((u) => [String(u.name), u.unit_name]));
	if (token !== M._production_token) return; // a newer render started meanwhile

	const crore = (v) => (v ? `₹ ${format_number(v, null, 2)} Cr` : "—");
	let html = M.stats_html([
		{ label: __("Products"), value: product_ids.length },
		{ label: __("Product Categories"), value: category_ids.length },
		{ label: __("Annual Turnover"), value: crore(frm.doc.annual_turnover_cr) },
		{ label: __("Abrasive Consumption / Year"), value: crore(frm.doc.abrasive_consumption_cr) },
	]);

	if (!rows.length) {
		html += `<p class="text-muted small" style="margin:4px 0 0;">${__(
			"No products yet. Add each product the customer makes and its production volume in the table below."
		)}</p>`;
		return wrapper.html(M.wrap(html));
	}

	// Products grouped by category
	const groups = {};
	for (const r of rows) {
		const p = product_map[String(r.product)] || {};
		const category = category_map[String(p.product_category)] || __("Other");
		(groups[category] = groups[category] || []).push({ row: r, name: p.product_name || r.product });
	}
	const volume = (r) => {
		if (!r.production_volume) return `<span class="text-muted">${__("Volume not given")}</span>`;
		const unit = unit_map[String(r.unit)] || "";
		return `<b style="font-size:16px;">${format_number(r.production_volume, null, 2)}</b> ${esc(unit)}${
			r.frequency ? ` <span class="text-muted">/ ${esc(__(r.frequency === "Annual" ? "Year" : r.frequency.replace(/ly$/, "")))}</span>` : ""
		}`;
	};
	html += Object.keys(groups)
		.sort()
		.map(
			(category) => `
		<div style="margin-top:14px;">
			<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
				<span class="indicator-pill blue">${esc(category)}</span>
				<span class="text-muted small">${__("{0} product(s)", [groups[category].length])}</span>
			</div>
			<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:10px;">
				${groups[category]
					.map(
						({ row, name }) => `
				<div style="border:1px solid var(--border-color); border-left:3px solid var(--blue-500); border-radius:var(--border-radius); padding:10px 12px; background:var(--fg-color);">
					<div style="font-weight:600; margin-bottom:4px;">${M.link("Customer Product", row.product, name)}</div>
					<div>${volume(row)}</div>
					${row.remarks ? `<div class="text-muted small" style="margin-top:4px;">${esc(row.remarks)}</div>` : ""}
				</div>`
					)
					.join("")}
			</div>
		</div>`
		)
		.join("");
	if (frm.doc.abrasive_consumption_details) {
		html += `<div class="text-muted small" style="margin-top:12px;"><b>${__("Abrasive Consumption")}:</b> ${esc(frm.doc.abrasive_consumption_details)}</div>`;
	}
	wrapper.html(M.wrap(html));
};

techpark.customer_master.render_commercial = function (frm) {
	if (!frm.fields_dict.commercial_html) return;
	const M = techpark.customer_master;
	const rows = frm.doc.turnovers || [];
	const total = rows.reduce((sum, r) => sum + (r.amount || 0), 0);
	frm.fields_dict.commercial_html.$wrapper.html(
		M.wrap(
			M.stats_html([
				{ label: "Turnover Records", value: rows.length },
				{ label: "Total Recorded", value: total ? format_currency(total) : "—" },
			])
		)
	);
};

// Technical Lead tab: small cards (main info of each lead) above the table; a click opens the row.
techpark.customer_master.render_technical = async function (frm) {
	if (!frm.fields_dict.technical_html) return;
	const M = techpark.customer_master;
	const esc = frappe.utils.escape_html;
	const $wrapper = frm.fields_dict.technical_html.$wrapper;
	const leads = frm.doc.technical_leads || [];
	const token = (M._lead_token = (M._lead_token || 0) + 1);
	if (!leads.length) return $wrapper.empty();

	const cat_ids = [...new Set(leads.map((r) => r.supplier_product_category).filter(Boolean))];
	const categories = cat_ids.length
		? Object.fromEntries((await M.get_list("Supplier Product Category", { name: ["in", cat_ids] }, ["name", "category_name"])).map((c) => [String(c.name), c.category_name]))
		: {};
	if (token !== M._lead_token) return;

	const money = (v) => (!v ? "" : v >= 1e7 ? `₹${(v / 1e7).toFixed(2)} Cr` : `₹${(v / 1e5).toFixed(1)} L`);
	// 2026-11-21: Principal share only (competitors are on the Technical Lead)
	const share_list = (r) => [
		...(r.principal_share ? [`${r.principal || __("Principal")} ${Math.round(r.principal_share)}%`] : []),
		// 2026-11-21: competitors are shown on the Technical Lead only (client)
	];
	const PROGRESS = { Approved: "green", "Evaluation Failed": "red", "Not Started": "gray", Quoted: "orange" };

	const cards = leads.map((r) => {
		const sub = [r.grinding_process, categories[String(r.supplier_product_category)]].filter(Boolean).map(esc).join(" · ");
		const demand = [money(r.annual_demand_amount), r.annual_quantity ? format_number(r.annual_quantity, null, 0) + " " + __("pcs") : ""].filter(Boolean).join(" · ");
		const shares = share_list(r).slice(0, 3).join("  ");
		const pills = [
			r.progress ? `<span class="indicator-pill ${PROGRESS[r.progress] || "blue"}">${esc(__(r.progress))}</span>` : "",
			r.current_status ? `<span class="indicator-pill ${r.stage === "Sales" ? "blue" : "orange"}">${esc(__(r.current_status))}</span>` : "",
		].join(" ");
		return `<div class="tp-lead-card" data-row="${esc(r.name)}" style="cursor:pointer; border:1px solid var(--border-color); border-top:3px solid #8e2229; border-radius:var(--border-radius); padding:10px 12px; background:var(--fg-color);">
			<div style="font-weight:700; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${esc(r.application || __("(no application)"))}</div>
			<div class="text-muted" style="font-size:11px; min-height:16px;">${sub}</div>
			${demand ? `<div style="font-size:12px; margin-top:6px;">${esc(demand)}</div>` : ""}
			${shares ? `<div class="text-muted" style="font-size:11px; margin-top:2px;">${esc(shares)}</div>` : ""}
			${pills.trim() ? `<div style="margin-top:8px;">${pills}</div>` : ""}
		</div>`;
	});
	$wrapper.html(`<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:10px; padding:12px 0 4px;">${cards.join("")}</div>`);
	$wrapper.find(".tp-lead-card").on("click", function () {
		const row = frm.fields_dict.technical_leads.grid.get_row($(this).data("row"));
		if (row) row.show_form();
	});
};

techpark.customer_master.contact_label = function (c) {
	return c.designation ? `${c.person_name} (${c.designation})` : c.person_name;
};

// Contact Person in the Visits table picks from this customer's active contacts
techpark.customer_master.set_contact_options = function (frm) {
	if (!frm.fields_dict.visits) return;
	const options = (frm.doc.contacts || [])
		.filter((c) => c.person_name && c.is_active)
		.map(techpark.customer_master.contact_label);
	frm.fields_dict.visits.grid.update_docfield_property("contact_person", "options", options);
};

// Visiting card: take a photo (or upload) of the front and back, OpenAI reads both, the
// user checks the details and they are filled into the form (techpark/visiting_card.py)
techpark.customer_master.upload_card = function (frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Scan Visiting Card"),
		fields: [
			{
				fieldname: "front",
				fieldtype: "Attach Image",
				label: __("Front"),
				reqd: 1,
				default: frm.doc.visiting_card,
			},
			{
				fieldname: "back",
				fieldtype: "Attach Image",
				label: __("Back"),
				description: __("Optional"),
				default: frm.doc.visiting_card_back,
			},
		],
		primary_action_label: __("Read Card"),
		primary_action(v) {
			dialog.hide();
			frm.set_value({ visiting_card: v.front, visiting_card_back: v.back || "" });
			// set_value is async: pass the images, not frm.doc
			techpark.customer_master.scan_card(frm, v.front, v.back);
		},
	});
	dialog.show();
};

techpark.customer_master.scan_card = function (frm, front, back) {
	frappe
		.call({
			method: "techpark.visiting_card.scan_card",
			args: { file_url: front, back_url: back || null },
			freeze: true,
			freeze_message: __("Reading visiting card..."),
		})
		.then((r) => r.message && techpark.customer_master.review_card(frm, r.message));
};

// Form field each card detail goes to (contact details also go to the Contacts table)
techpark.customer_master.CARD_TARGETS = {
	customer_name: "customer_name",
	person_name: "primary_contact_name",
	phone: "primary_contact_phone",
	email: "primary_contact_email",
	address: "customer_address",
	city: "plant_location",
	state: "state",
	pincode: "pincode",
	gstin: "gstin",
};

techpark.customer_master.review_card = function (frm, card) {
	const phones = card.phones || [];
	const values = {
		customer_name: card.company_name,
		person_name: card.person_name,
		designation: card.designation,
		department: card.department,
		phone: phones[0] || "",
		other_phones: phones.slice(1).join(", "),
		email: card.email,
		website: card.website,
		address: card.address,
		city: card.city,
		state: card.state,
		pincode: card.pincode,
		gstin: card.gstin,
	};
	const labels = {
		customer_name: __("Customer Name"),
		person_name: __("Contact Name"),
		designation: __("Designation"),
		department: __("Department"),
		phone: __("Phone"),
		other_phones: __("Other Phones"),
		email: __("Email"),
		website: __("Website"),
		address: __("Address"),
		city: __("Location / City"),
		state: __("State"),
		pincode: __("Pincode"),
		gstin: __("GSTIN"),
	};
	const targets = techpark.customer_master.CARD_TARGETS;
	const fields = Object.keys(labels).map((key) => {
		const current = targets[key] && frm.doc[targets[key]];
		return {
			fieldname: key,
			label: labels[key],
			fieldtype: key === "address" ? "Small Text" : "Data",
			default: values[key] || "",
			// Show what the form has now when the card says something else
			description: current && current !== values[key] ? __("Now: {0}", [frappe.utils.escape_html(current)]) : "",
		};
	});
	fields.splice(7, 0, { fieldtype: "Column Break" });

	const dialog = new frappe.ui.Dialog({
		title: __("Visiting Card Details"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Check the details read from the card. Clear a field to keep what the form has now."
				)}</p>`,
			},
			...fields,
		],
		primary_action_label: __("Fill Form"),
		primary_action(v) {
			dialog.hide();
			techpark.customer_master.fill_from_card(frm, v);
		},
	});
	dialog.show();
};

techpark.customer_master.fill_from_card = function (frm, v) {
	const targets = techpark.customer_master.CARD_TARGETS;
	// Phone field takes one number: digits and a leading +
	if (v.phone) v.phone = v.phone.replace(/(?!^\+)[^\d]/g, "").slice(0, 15);
	for (const [key, field] of Object.entries(targets)) {
		if (v[key]) frm.set_value(field, v[key]);
	}

	if (!v.person_name) return;
	const phones = [v.phone, v.other_phones].filter(Boolean).join(", ");
	const name = v.person_name.trim().toLowerCase();
	let row = (frm.doc.contacts || []).find((c) => (c.person_name || "").trim().toLowerCase() === name);
	if (!row) {
		row = frm.add_child("contacts", {
			person_name: v.person_name,
			is_active: 1,
			is_primary: (frm.doc.contacts || []).some((c) => c.is_primary) ? 0 : 1,
		});
	}
	const details = { designation: v.designation, department: v.department, phone: phones, email: v.email };
	if (v.website && !row.notes) details.notes = v.website;
	for (const [field, value] of Object.entries(details)) {
		if (value) row[field] = value;
	}
	frm.refresh_field("contacts");
	techpark.customer_master.set_contact_options(frm);
	frappe.show_alert({ message: __("Filled from the visiting card. Save the customer."), indicator: "green" });
};

techpark.customer_master.VISIT_PERIODS = {
	all: { label: __("All"), range: () => null },
	week: { label: __("This Week"), range: () => [moment().startOf("isoWeek"), moment().endOf("isoWeek")] },
	month: { label: __("This Month"), range: () => [moment().startOf("month"), moment().endOf("month")] },
	last_month: {
		label: __("Last Month"),
		range: () => [moment().subtract(1, "month").startOf("month"), moment().subtract(1, "month").endOf("month")],
	},
};

techpark.customer_master.in_period = function (frm, row) {
	const range = techpark.customer_master.VISIT_PERIODS[frm.__visit_period || "all"].range();
	if (!range || !row.visit_date) return true; // unsaved rows without a date always show
	const d = moment(row.visit_date);
	return d.isSameOrAfter(range[0], "day") && d.isSameOrBefore(range[1], "day");
};

// Filter bar + tiles above the Visits table; the table rows are filtered to the same period
techpark.customer_master.render_visits = function (frm) {
	if (!frm.fields_dict.visits_html) return;
	const M = techpark.customer_master;
	const period = frm.__visit_period || "all";
	const visits = (frm.doc.visits || []).filter((v) => M.in_period(frm, v));
	const latest = [...visits].filter((v) => v.visit_date).sort((a, b) => (a.visit_date < b.visit_date ? 1 : -1))[0];

	const buttons = Object.entries(M.VISIT_PERIODS)
		.map(
			([key, p]) =>
				`<button type="button" class="btn btn-xs ${key === period ? "btn-primary" : "btn-default"} tp-visit-period" data-period="${key}">${p.label}</button>`
		)
		.join(" ");

	let html = `<div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
		<span class="text-muted small" style="margin-right:4px;">${__("Show visits")}:</span>${buttons}
		${frappe.model.can_create("Daily Visit Report") ? `<button type="button" class="btn btn-sm btn-primary tp-add-visit" style="margin-left:auto;">+ ${__("Add Visit")}</button>` : ""}
	</div>`;
	html += M.stats_html([
		{ label: __("Visits"), value: visits.length },
		{ label: __("Submitted"), value: visits.filter((v) => v.status === "Submitted").length },
		{ label: __("Won"), value: visits.filter((v) => v.lead_status === "Won").length },
		{ label: __("Last Visit"), value: latest ? frappe.datetime.str_to_user(latest.visit_date) : "—" },
		{ label: __("Latest Lead Status"), value: latest ? latest.lead_status : "—" },
	]);
	html += `<div class="tp-principal-status" style="margin-bottom:12px;"></div>`;

	const wrapper = frm.fields_dict.visits_html.$wrapper;
	wrapper.html(M.wrap(html));
	// A new visit (DVR) for this customer: customer filled in, then contacts / open lines load on the visit
	wrapper.find(".tp-add-visit").on("click", () => {
		frappe.new_doc("Daily Visit Report", {
			customer: frm.doc.name,
			customer_name: frm.doc.customer_name,
			visit_date: frappe.datetime.get_today(),
		});
	});
	wrapper.find(".tp-visit-period").on("click", function () {
		frm.__visit_period = $(this).data("period");
		M.render_visits(frm);
	});
	M.filter_visit_rows(frm);
	M.render_principal_status(frm, wrapper.find(".tp-principal-status"), visits);
};

// Latest status of each application line (application + principal + category + spec) over the visits shown.
techpark.customer_master.render_principal_status = async function (frm, $target, visits) {
	const dates = Object.fromEntries(visits.filter((v) => v.record).map((v) => [v.record, v.visit_date || ""]));
	const records = Object.keys(dates);
	if (!records.length) return;
	const rows = await frappe.xcall("frappe.client.get_list", {
		doctype: "DVR Principal",
		parent: "Daily Visit Report",
		filters: [["parent", "in", records]],
		fields: ["parent", "application", "spec", "opportunity", "principal", "supplier_product_category", "category_name", "stage", "development_status", "sales_status", "progress"],
		limit_page_length: 0,
	});
	const latest = {};
	for (const r of rows.sort((a, b) => (dates[a.parent] < dates[b.parent] ? 1 : -1))) {
		const key = `${r.application || ""}|${r.principal}|${r.supplier_product_category || ""}|${r.spec || ""}`;
		if (!latest[key]) latest[key] = r;
	}
	const esc = frappe.utils.escape_html;
	const color = (s) =>
		["Bulk Trial PO", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up", "Regularization"].includes(s) ? "green"
		: s === "Enquiry Follow-up" ? "blue"
		: ["Cancelled", "Trial Failed"].includes(s) ? "red"
		: s === "On Hold" ? "gray"
		: s === "Successful Trial" ? "purple"
		: "blue";
	const body = Object.values(latest)
		.map((r) => {
			const status = (r.stage === "Sales" && r.sales_status) || r.development_status || "";
			return `<tr>
				<td>${r.opportunity ? `<a href="/desk/tp-opportunity/${encodeURIComponent(r.opportunity)}">${esc(r.application || "")}</a>` : esc(r.application || "")}</td>
				<td>${esc(r.principal)}</td>
				<td>${esc([r.category_name, r.spec].filter(Boolean).join(" · "))}</td>
				<td>${esc(__(r.stage || ""))}</td>
				<td><span class="indicator-pill ${color(status)}">${esc(__(status))}</span></td>
				<td style="text-align:right;">${r.progress || 0}%</td>
				<td><a href="/desk/daily-visit-report/${encodeURIComponent(r.parent)}">${frappe.datetime.str_to_user(dates[r.parent])}</a></td>
			</tr>`;
		})
		.join("");
	$target.html(`<div class="control-label" style="margin-bottom:6px;">${__("Application-wise Status")}</div>
		<div style="overflow-x:auto;"><table class="table table-bordered table-sm" style="font-size:12px; margin:0;">
			<thead><tr><th>${__("Application / Line")}</th><th>${__("Principal")}</th><th>${__("Category · Spec")}</th><th>${__("Stage")}</th>
				<th>${__("Status")}</th><th style="text-align:right;">${__("Progress")}</th><th>${__("Last Visit")}</th></tr></thead>
			<tbody>${body}</tbody>
		</table></div>`);
};

techpark.customer_master.filter_visit_rows = function (frm) {
	const grid = frm.fields_dict.visits && frm.fields_dict.visits.grid;
	if (!grid) return;
	// Let the grid finish (re)drawing its rows before hiding the ones outside the period
	setTimeout(() => {
		(grid.grid_rows || []).forEach((gr) => $(gr.wrapper).toggle(techpark.customer_master.in_period(frm, gr.doc)));
	}, 0);
};

frappe.provide("techpark");
// 2026-11-26: changing a Technical Lead that has visits: a dialog lists the changes and the visits it affects;
// "Yes" saves and updates those visits, "No" does not save. (Here, not in techpark.js: form scripts reload with each build.)
techpark.LEAD_FIELDS = ["principal", "product", "application_master", "production_line", "supplier_product_category", "size", "spec"];
techpark.lead_snapshot = function (row) {
	const out = {};
	for (const f of techpark.LEAD_FIELDS) out[f] = (row[f] || "").toString().trim();
	return out;
};
techpark.ask_lead_visits = async function (items) {
	const changed = items
		.map((i) => ({ ...i, now: techpark.lead_snapshot(i.row) }))
		.map((i) => ({ ...i, fields: techpark.LEAD_FIELDS.filter((f) => i.saved[f] !== i.now[f]) }))
		.filter((i) => i.fields.length);
	if (!changed.length) return true;
	const visits = await frappe.xcall("techpark.application.lead_visit_list", { leads: changed.map((i) => i.lead) });
	const hit = changed.filter((i) => (visits[i.lead] || []).length);
	if (!hit.length) return true;
	const esc = frappe.utils.escape_html;
	// Links show their title where they have one (product / application / category names)
	const show = async (doctype, f, v) => {
		const df = frappe.meta.get_docfield(doctype, f);
		if (!v || !df || df.fieldtype !== "Link") return v || "—";
		const title = await frappe.db.get_value(df.options, v, frappe.get_meta(df.options)?.title_field || "name").then((r) => r.message && Object.values(r.message)[0]).catch(() => null);
		return title || v;
	};
	let total = 0;
	const blocks = [];
	for (const i of hit) {
		const list = visits[i.lead];
		total += list.length;
		const rows = [];
		for (const f of i.fields) {
			rows.push(`<tr><td class="text-muted">${esc(__(frappe.meta.get_label(i.doctype, f)))}</td>
				<td><s class="text-muted">${esc(await show(i.doctype, f, i.saved[f]))}</s></td>
				<td><b>${esc(await show(i.doctype, f, i.now[f]))}</b></td></tr>`);
		}
		const chips = list
			.map((v) => `<a href="/app/daily-visit-report/${encodeURIComponent(v.name)}" target="_blank" class="indicator-pill ${v.docstatus === 1 ? "blue" : "gray"}" style="margin:2px">${esc(v.name)} · ${frappe.datetime.str_to_user(v.visit_date)}${v.dvr_stage ? " · " + esc(__(v.dvr_stage)) : ""}</a>`)
			.join("");
		blocks.push(`<div style="border:1px solid var(--border-color);border-radius:10px;padding:12px;margin-bottom:12px">
			<div style="font-weight:600;margin-bottom:8px">${esc(i.lead)}</div>
			<table class="table table-sm" style="margin-bottom:8px"><tr><th>${__("Field")}</th><th>${__("Was")}</th><th>${__("Now")}</th></tr>${rows.join("")}</table>
			<div class="text-muted small" style="margin-bottom:4px">${__("Visits that will be updated ({0})", [list.length])}</div>
			<div>${chips}</div></div>`);
	}
	return new Promise((resolve) => {
		let answered = false;
		const d = new frappe.ui.Dialog({
			title: __("Technical Lead changed"),
			size: "large",
			fields: [{
				fieldtype: "HTML",
				options: `<div class="alert alert-warning" style="margin-bottom:12px">${__("This will affect <b>{0}</b> visit(s) (DVR). They will be changed to the new data.", [total])}</div>
					${blocks.join("")}
					<p style="margin:0">${__("Do you want to submit?")}</p>`,
			}],
			primary_action_label: __("Yes, save and update {0} visit(s)", [total]),
			primary_action() {
				answered = true;
				d.hide();
				resolve(true);
			},
			secondary_action_label: __("No"),
			secondary_action() {
				d.hide();
			},
		});
		d.onhide = () => {
			if (!answered) {
				frappe.show_alert({ message: __("Not saved: the Technical Lead was not changed."), indicator: "orange" });
				resolve(false);
			}
		};
		d.show();
	});
};
