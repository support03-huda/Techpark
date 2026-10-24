// Copyright (c) 2026, Techpark International
// Helpers shared by the TechPark forms.

frappe.provide("techpark");

// An entry locked for salespeople (TechPark Settings > Lock Entries After) opens read-only with a note.
techpark.show_lock = function (frm) {
	if (!(frm.doc.__onload || {}).locked) return;
	frm.set_intro(
		__("This entry is locked: it is older than the edit limit. Ask a Sales Manager or an admin to change it."),
		"orange"
	);
	frm.disable_form();
};
