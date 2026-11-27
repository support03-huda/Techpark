// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// Opened from a visit's "Create a new Technical Lead": after saving, Frappe returns to that
// visit and puts this lead in the row it was created from.

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);

// 2026-11-27 (client): a new Technical Lead shows Progress = the TP Lead Progress Default (To Start; can be changed)
// and Stage = Development straight away
techpark.lead_defaults = function (doctype, name) {
	const d = locals[doctype][name];
	const values = {};
	if (!d.progress && frappe.boot.techpark_default_lead_progress) values.progress = frappe.boot.techpark_default_lead_progress;
	if (!d.stage) values.stage = techpark.K("TP Stage", "Development");
	if (Object.keys(values).length) frappe.model.set_value(doctype, name, values);
};

frappe.ui.form.on("TP Technical Lead", {
	onload(frm) {
		if (frm.is_new()) techpark.lead_defaults(frm.doctype, frm.docname); // 2026-11-27
	},
	setup(frm) {
		frm.set_query("principal", () => ({ filters: { is_active: 1 } }));
		frm.set_query("supplier_product_category", () => ({
			filters: { principal: frm.doc.principal || "", is_active: 1 },
		}));
	},
	principal(frm) {
		frm.set_value("supplier_product_category", "");
	},
	// 2026-11-26: a change that reaches the lead's visits asks first ("This will affect N visits. Do you want to submit?")
	refresh(frm) {
		frm._lead_saved = !frm.is_new() && techpark.lead_snapshot ? techpark.lead_snapshot(frm.doc) : null;
		techpark.lead_freeze(frm); // 2026-11-27
	},
	async validate(frm) {
		if (!frm._lead_saved || !techpark.ask_lead_visits) return;
		const ok = await techpark.ask_lead_visits([{ lead: frm.doc.name, saved: frm._lead_saved, row: frm.doc, doctype: frm.doctype }]);
		if (!ok) frappe.validated = false;
	},
});

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

// 2026-11-27: Freeze / Unfreeze (admins: TechPark Settings > Admin Roles); a frozen lead is read only for everyone else
techpark.lead_freeze = function (frm) {
	if (frm.is_new()) return;
	// 2026-11-27: decided on the server: Freeze = may edit the lead, Unfreeze = Admin Roles
	const can_freeze = !!(frm.doc.__onload || {}).can_freeze, can_unfreeze = !!(frm.doc.__onload || {}).can_unfreeze;
	if (frm.doc.is_frozen) {
		frm.set_intro(
			__("Frozen by {0} on {1}: no changes until an admin presses Unfreeze.", [
				frappe.utils.escape_html(frappe.user.full_name(frm.doc.frozen_by) || frm.doc.frozen_by || ""),
				frm.doc.frozen_on ? frappe.datetime.str_to_user(frm.doc.frozen_on) : "",
			]),
			"blue"
		);
		frm.disable_form(); // 2026-11-27: read only for everybody, admins too, until Unfreeze
	} else {
		frm.set_intro("");
	}
	const set = (frozen) =>
		frappe.xcall("techpark.techpark.doctype.tp_technical_lead.tp_technical_lead.set_frozen", { name: frm.doc.name, frozen })
			// 2026-11-27: a full reload, since the read-only state set while frozen stays on the open page after Unfreeze
			.then(() => window.location.reload());
	if (frm.doc.is_frozen) {
		if (can_unfreeze) frm.add_custom_button(__("Unfreeze"), () => set(0));
	} else if (can_freeze) {
		frm.add_custom_button(__("Freeze"), () =>
			frappe.confirm(__("Freeze {0}? Nobody can change it until an admin presses Unfreeze.", [frappe.utils.escape_html(frm.doc.name)]), () => set(1))
		);
	}
};
