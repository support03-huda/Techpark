// Copyright (c) 2026, Techpark International
// Plants / Production / Commercial / Visits tabs: summary tiles above editable
// tables. The tables are synced to the real Plant, Customer Product Production,
// Customer Turnover and Daily Visit Report records on save
// (techpark/customer_sync.py). The Products tab is a read-only summary.

frappe.ui.form.on("TP Customer", {
	refresh(frm) {
		const M = techpark.customer_master;
		// Only this customer's plants in the Production / Commercial / Visits tables
		for (const table of ["production", "turnovers", "visits"]) {
			if (frm.fields_dict[table]) {
				frm.set_query("plant", table, () => ({ filters: { customer: frm.doc.name || "" } }));
			}
		}
		M.set_contact_options(frm);
		M.render_plants(frm);
		if (frm.is_new()) return;
		M.render_production(frm);
		M.render_commercial(frm);
		M.render_products(frm);
		M.render_visits(frm);
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
});
frappe.ui.form.on("TP Customer Turnover", {
	turnovers_add: (frm) => techpark.customer_master.render_commercial(frm),
	turnovers_remove: (frm) => techpark.customer_master.render_commercial(frm),
	amount: (frm) => techpark.customer_master.render_commercial(frm),
});
frappe.ui.form.on("TP Customer Visit", {
	visits_add(frm, cdt, cdn) {
		// Pre-fill the primary contact and, if there is only one, the plant
		const primary = (frm.doc.contacts || []).find((c) => c.is_primary);
		if (primary) frappe.model.set_value(cdt, cdn, "contact_person", techpark.customer_master.contact_label(primary));
		const active = (frm.doc.plants || []).filter((p) => p.is_active && p.record);
		if (active.length === 1) frappe.model.set_value(cdt, cdn, "plant", active[0].record);
		techpark.customer_master.render_visits(frm);
	},
	visits_remove: (frm) => techpark.customer_master.render_visits(frm),
	visit_date: (frm) => techpark.customer_master.render_visits(frm),
	lead_status(frm, cdt, cdn) {
		if (locals[cdt][cdn].lead_status === "Won") frappe.model.set_value(cdt, cdn, "lead_stage", "Order Received");
		techpark.customer_master.render_visits(frm);
	},
});
frappe.ui.form.on("Company contacts", {
	name1: (frm) => techpark.customer_master.set_contact_options(frm),
	designation: (frm) => techpark.customer_master.set_contact_options(frm),
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

techpark.customer_master.plant_names = function (frm) {
	const names = {};
	(frm.doc.plants || []).forEach((p) => p.record && (names[p.record] = p.plant_name));
	return names;
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

techpark.customer_master.render_production = function (frm) {
	if (!frm.fields_dict.production_html) return;
	const M = techpark.customer_master;
	frm.fields_dict.production_html.$wrapper.html(
		M.wrap(
			M.stats_html([
				{ label: "Active Plants", value: (frm.doc.plants || []).filter((p) => p.is_active).length },
				{ label: "Production Lines", value: (frm.doc.production || []).length },
				{
					label: "Annual Turnover",
					value: frm.doc.annual_turnover_cr ? `₹${frm.doc.annual_turnover_cr} Cr` : "—",
				},
			])
		)
	);
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

// Products = the distinct products in the Production tab (read-only summary)
techpark.customer_master.render_products = async function (frm) {
	if (!frm.fields_dict.products_html) return;
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.products_html.$wrapper;
	const plant_names = M.plant_names(frm);

	const seen = {};
	(frm.doc.production || []).forEach((r) => {
		if (r.product && !seen[r.product]) seen[r.product] = r.plant;
	});
	const product_ids = Object.keys(seen);

	const products = product_ids.length
		? await M.get_list("Customer Product", { name: ["in", product_ids] }, ["name", "product_name", "product_category", "active"])
		: [];
	const product_map = {};
	products.forEach((p) => (product_map[p.name] = p));

	const category_ids = [...new Set(products.map((p) => p.product_category).filter(Boolean))];
	const categories = category_ids.length
		? await M.get_list("Product Category", { name: ["in", category_ids] }, ["name", "category_name"])
		: [];
	const category_map = {};
	categories.forEach((c) => (category_map[c.name] = c.category_name));

	let html = M.stats_html([{ label: "Distinct Products", value: product_ids.length }]);
	html += M.table_html(
		["Product", "Category", "Plant", "Status"],
		product_ids.map((pid) => {
			const prod = product_map[pid] || {};
			return [
				M.link("Customer Product", pid, prod.product_name || pid),
				frappe.utils.escape_html(category_map[prod.product_category] || ""),
				frappe.utils.escape_html(plant_names[seen[pid]] || seen[pid] || ""),
				M.badge(prod.active ? "Active" : "Inactive", prod.active ? "green" : "gray"),
			];
		})
	);
	html += `<p class="text-muted small">${__("Products come from the Production tab — add a production row to add a product here.")}</p>`;
	wrapper.html(M.wrap(html));
};

techpark.customer_master.contact_label = function (c) {
	return c.designation ? `${c.name1} (${c.designation})` : c.name1;
};

// Contact Person in the Visits table picks from this customer's Contacts tab
techpark.customer_master.set_contact_options = function (frm) {
	if (!frm.fields_dict.visits) return;
	const options = (frm.doc.contacts || []).filter((c) => c.name1).map(techpark.customer_master.contact_label);
	frm.fields_dict.visits.grid.update_docfield_property("contact_person", "options", options);
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
	</div>`;
	html += M.stats_html([
		{ label: __("Visits"), value: visits.length },
		{ label: __("Submitted"), value: visits.filter((v) => v.status === "Submitted").length },
		{ label: __("Won"), value: visits.filter((v) => v.lead_status === "Won").length },
		{ label: __("Last Visit"), value: latest ? frappe.datetime.str_to_user(latest.visit_date) : "—" },
		{ label: __("Latest Lead Status"), value: latest ? latest.lead_status : "—" },
	]);
	html += `<p class="text-muted small" style="margin:0;">${__(
		"Add a row to log a visit — it is saved as a Daily Visit Report. On submitted visits you can still update Lead Status and Lead Stage as the lead progresses; anything else is changed from the DVR itself (click its DVR ID)."
	)}</p>`;

	const wrapper = frm.fields_dict.visits_html.$wrapper;
	wrapper.html(M.wrap(html));
	wrapper.find(".tp-visit-period").on("click", function () {
		frm.__visit_period = $(this).data("period");
		M.render_visits(frm);
	});
	M.filter_visit_rows(frm);
};

techpark.customer_master.filter_visit_rows = function (frm) {
	const grid = frm.fields_dict.visits && frm.fields_dict.visits.grid;
	if (!grid) return;
	// Let the grid finish (re)drawing its rows before hiding the ones outside the period
	setTimeout(() => {
		(grid.grid_rows || []).forEach((gr) => $(gr.wrapper).toggle(techpark.customer_master.in_period(frm, gr.doc)));
	}, 0);
};
