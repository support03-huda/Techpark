// Last edited: 2026-11-27
// Copyright (c) 2026, Techpark International
// Helpers shared by the TechPark forms.

// 2026-11-27: master values by App Key (renameable); also in public/js/techpark.js
frappe.provide("techpark");
techpark.K = techpark.K || ((m, k) => ((frappe.boot.techpark_keys || {})[m] || {})[k] || k);
techpark.colour = techpark.colour || ((m, v, f) => ((frappe.boot.techpark_colours || {})[m] || {})[v] || f || "gray");
techpark.key_of = techpark.key_of || ((m, n) => { const x = (frappe.boot.techpark_keys || {})[m] || {}; return Object.keys(x).find((k) => x[k] === n) || n; });
techpark.result_of = techpark.result_of || ((s) => (frappe.boot.techpark_status_results || {})[s]);

frappe.provide("techpark");

// 2026-11-27: a master value the app's logic uses, by its App Key (the client may rename it):
// techpark.K("TP Stage", "Sales") -> the current name. Colour of a value from its master.
techpark.K = function (master, key) {
	return ((frappe.boot.techpark_keys || {})[master] || {})[key] || key;
};
techpark.colour = function (master, value, fallback) {
	return ((frappe.boot.techpark_colours || {})[master] || {})[value] || fallback || "gray";
};
// App Key of a value's current name; what a Development / Sales Status counts as (Open / Won / Lost / On Hold)
techpark.key_of = function (master, name) {
	const m = (frappe.boot.techpark_keys || {})[master] || {};
	return Object.keys(m).find((k) => m[k] === name) || name;
};
techpark.result_of = function (status) {
	return (frappe.boot.techpark_status_results || {})[status];
};

// 2026-11-27 (client): a master's list shows its ID (DVS-0001) as the ID; Frappe's name column (= the name) is hidden
(frappe.boot.techpark_masters || []).forEach((doctype) => {
	frappe.listview_settings[doctype] = Object.assign(frappe.listview_settings[doctype] || {}, { hide_name_column: true });
});

// An entry locked for salespeople (TechPark Settings > Lock Entries After) opens read-only with a note.
techpark.show_lock = function (frm) {
	if (!(frm.doc.__onload || {}).locked) return;
	frm.set_intro(
		__("This entry is locked: it is older than the edit limit. Ask a Sales Manager or an admin to change it."),
		"orange"
	);
	frm.disable_form();
};
