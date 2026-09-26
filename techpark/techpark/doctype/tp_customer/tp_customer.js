// Copyright (c) 2026, Techpark International
// Renders the Plants / Production / Products / Commercial / Visits tabs with data
// pulled live from Plant, Customer Product Production, Customer Product,
// Product Category, Customer Turnover and Daily Visit Report — all via the standard whitelisted
// frappe.client.get_list, no custom server APIs.

frappe.ui.form.on("TP Customer", {
	refresh(frm) {
		if (frm.is_new()) return;
		techpark.customer_master.render(frm);
	},
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
	return `<div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px;">${tiles}</div>`;
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

techpark.customer_master.add_button_html = function (label) {
	return `<div style="margin-top:8px;">
		<button type="button" class="btn btn-sm btn-default tp-add-btn">
			<svg class="icon icon-xs" style="margin-right:4px; vertical-align:-1px;"><use href="#icon-add"></use></svg>${frappe.utils.escape_html(label)}
		</button>
	</div>`;
};

techpark.customer_master.bind_add_button = function (wrapper, doctype, defaults) {
	wrapper.find(".tp-add-btn").on("click", () => frappe.new_doc(doctype, defaults));
};

techpark.customer_master.wrap = function (html) {
	return `<div style="padding:16px 2px 4px;">${html}</div>`;
};

techpark.customer_master.link = function (doctype, name, label) {
	return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${frappe.utils.escape_html(label || name)}</a>`;
};

techpark.customer_master.render = async function (frm) {
	const M = techpark.customer_master;
	try {
		const plants = await M.get_list(
			"Plant",
			{ customer: frm.doc.name },
			["name", "plant_name", "plant_location", "state", "is_active"]
		);
		const plant_map = {};
		plants.forEach((p) => (plant_map[p.name] = p));

		const production = await M.get_list(
			"Customer Product Production",
			{ customer: frm.doc.name },
			["name", "plant", "department", "product", "production_volume", "unit", "frequency"]
		);

		const product_ids = [...new Set(production.map((r) => r.product).filter(Boolean))];
		const products = product_ids.length
			? await M.get_list("Customer Product", { name: ["in", product_ids] }, [
					"name",
					"product_name",
					"product_category",
					"active",
			  ])
			: [];
		const product_map = {};
		products.forEach((p) => (product_map[p.name] = p));

		const category_ids = [...new Set(products.map((p) => p.product_category).filter(Boolean))];
		const categories = category_ids.length
			? await M.get_list("Product Category", { name: ["in", category_ids] }, ["name", "category_name"])
			: [];
		const category_map = {};
		categories.forEach((c) => (category_map[c.name] = c.category_name));

		const turnovers = await M.get_list(
			"Customer Turnover",
			{ customer: frm.doc.name },
			["name", "plant", "financial_year", "amount", "unit", "remarks"]
		);

		M.render_plants(frm, plants);
		M.render_production(frm, production, plant_map, product_map);
		M.render_products(frm, production, product_map, category_map, plant_map);
		M.render_commercial(frm, turnovers, plant_map);

		const visits = await M.get_list(
			"Daily Visit Report",
			{ customer: frm.doc.name, docstatus: ["<", 2] },
			["name", "visit_date", "plant", "visit_purpose", "lead_status", "stage_completed", "next_action", "employee_name", "docstatus"]
		);
		M.render_visits(frm, visits, plant_map);
	} catch (e) {
		console.error("Customer Master: failed to load linked records", e);
	}
};

techpark.customer_master.render_plants = function (frm, plants) {
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.plants_html.$wrapper;
	const active = plants.filter((p) => p.is_active).length;

	let html = M.stats_html([
		{ label: "Total Plants", value: plants.length },
		{ label: "Active Plants", value: active },
	]);
	html += M.table_html(
		["Plant", "Location", "State", "Status"],
		plants.map((p) => [
			M.link("Plant", p.name, p.plant_name),
			frappe.utils.escape_html(p.plant_location || ""),
			frappe.utils.escape_html(p.state || ""),
			M.badge(p.is_active ? "Active" : "Inactive", p.is_active ? "green" : "gray"),
		])
	);
	html += M.add_button_html("Add Plant");
	wrapper.html(M.wrap(html));
	M.bind_add_button(wrapper, "Plant", { customer: frm.doc.name });
};

techpark.customer_master.render_production = function (frm, rows, plant_map, product_map) {
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.production_html.$wrapper;
	const active_plants = Object.values(plant_map).filter((p) => p.is_active).length;

	let html = M.stats_html([
		{ label: "Active Plants", value: active_plants },
		{ label: "Production Lines", value: rows.length },
		{
			label: "Annual Turnover",
			value: frm.doc.annual_turnover_cr ? `₹${frm.doc.annual_turnover_cr} Cr` : "—",
		},
	]);
	html += M.table_html(
		["Plant", "Department", "Product", "Monthly Qty", "Unit", "Frequency"],
		rows.map((r) => [
			frappe.utils.escape_html(plant_map[r.plant]?.plant_name || r.plant || ""),
			frappe.utils.escape_html(r.department || ""),
			r.product ? M.link("Customer Product Production", r.name, product_map[r.product]?.product_name || r.product) : "",
			r.production_volume != null ? frappe.utils.escape_html(String(r.production_volume)) : "",
			frappe.utils.escape_html(r.unit || ""),
			frappe.utils.escape_html(r.frequency || ""),
		])
	);
	html += M.add_button_html("Add Production");
	wrapper.html(M.wrap(html));
	M.bind_add_button(wrapper, "Customer Product Production", { customer: frm.doc.name });
};

techpark.customer_master.render_products = function (frm, production, product_map, category_map, plant_map) {
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.products_html.$wrapper;

	const seen = {};
	production.forEach((r) => {
		if (r.product && !seen[r.product]) seen[r.product] = r.plant;
	});
	const product_ids = Object.keys(seen);

	let html = M.stats_html([{ label: "Distinct Products", value: product_ids.length }]);
	html += M.table_html(
		["Product", "Category", "Plant", "Status"],
		product_ids.map((pid) => {
			const prod = product_map[pid] || {};
			return [
				M.link("Customer Product", pid, prod.product_name || pid),
				frappe.utils.escape_html(category_map[prod.product_category] || ""),
				frappe.utils.escape_html(plant_map[seen[pid]]?.plant_name || ""),
				M.badge(prod.active ? "Active" : "Inactive", prod.active ? "green" : "gray"),
			];
		})
	);
	html += M.add_button_html("Add Production");
	wrapper.html(M.wrap(html));
	M.bind_add_button(wrapper, "Customer Product Production", { customer: frm.doc.name });
};

techpark.customer_master.render_commercial = function (frm, rows, plant_map) {
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.commercial_html.$wrapper;
	const total = rows.reduce((sum, r) => sum + (r.amount || 0), 0);

	let html = M.stats_html([
		{ label: "Turnover Records", value: rows.length },
		{ label: "Total Recorded", value: total ? format_currency(total) : "—" },
	]);
	html += M.table_html(
		["Financial Year", "Plant", "Amount", "Unit", "Remarks"],
		rows.map((r) => [
			frappe.utils.escape_html(r.financial_year || ""),
			frappe.utils.escape_html(plant_map[r.plant]?.plant_name || ""),
			r.amount != null ? frappe.utils.escape_html(String(r.amount)) : "",
			frappe.utils.escape_html(r.unit || ""),
			frappe.utils.escape_html(r.remarks || ""),
		])
	);
	html += M.add_button_html("Add Turnover");
	wrapper.html(M.wrap(html));
	M.bind_add_button(wrapper, "Customer Turnover", { customer: frm.doc.name });
};

techpark.customer_master.render_visits = function (frm, visits, plant_map) {
	const M = techpark.customer_master;
	const wrapper = frm.fields_dict.visits_html.$wrapper;
	visits.sort((a, b) => (a.visit_date < b.visit_date ? 1 : -1));
	const status_colors = { Prospect: "orange", Won: "green", Lost: "red", "On Hold": "gray" };

	let html = M.stats_html([
		{ label: "Total Visits", value: visits.length },
		{ label: "Last Visit", value: visits.length ? frappe.datetime.str_to_user(visits[0].visit_date) : "—" },
		{ label: "Latest Lead Status", value: visits.length ? visits[0].lead_status : "—" },
	]);
	html += M.table_html(
		["DVR ID", "Date", "Plant", "Purpose", "Lead Status", "Stage", "Next Action", "Employee"],
		visits.map((v) => [
			M.link("Daily Visit Report", v.name),
			frappe.datetime.str_to_user(v.visit_date),
			frappe.utils.escape_html(plant_map[v.plant]?.plant_name || v.plant || ""),
			frappe.utils.escape_html(v.visit_purpose || ""),
			v.docstatus === 0 ? M.badge("Draft", "gray") : M.badge(v.lead_status, status_colors[v.lead_status] || "blue"),
			`${v.stage_completed || 0}%`,
			frappe.utils.escape_html(v.next_action || ""),
			frappe.utils.escape_html(v.employee_name || ""),
		])
	);
	html += M.add_button_html("New DVR");
	wrapper.html(M.wrap(html));
	M.bind_add_button(wrapper, "Daily Visit Report", { customer: frm.doc.name });
};
