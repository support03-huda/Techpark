// Copyright (c) 2026, Techpark International
// Pending Work list: the sheet's columns as coloured Category pills, open work first.

const TP_PW_CATEGORY_COLORS = {
	"Costing & Offers": "pink",
	"SO's": "blue",
	"OC's to make": "purple",
	"Routine monthly work": "orange",
	"Desp. / invoices (Techpark)": "cyan",
	"Despatches (Direct)": "green",
	Others: "gray",
};

frappe.listview_settings["TP Pending Work"] = {
	add_fields: ["status", "due_date", "priority", "category"],
	filters: [["status", "in", ["Open", "In Progress"]]],
	hide_name_column: true,

	get_indicator(doc) {
		const today = frappe.datetime.get_today();
		if (doc.status === "Done") return [__("Done"), "green", "status,=,Done"];
		if (doc.status === "Cancelled") return [__("Cancelled"), "gray", "status,=,Cancelled"];
		if (doc.due_date && doc.due_date < today) return [__("Overdue"), "red", "due_date,<,Today"];
		if (doc.due_date === today) return [__("Due Today"), "orange", "due_date,=,Today"];
		return [__(doc.status), doc.status === "In Progress" ? "blue" : "yellow", `status,=,${doc.status}`];
	},

	formatters: {
		category(value) {
			if (!value) return "";
			const color = TP_PW_CATEGORY_COLORS[value] || "gray";
			return `<span class="indicator-pill no-indicator-dot ${color}" title="${frappe.utils.escape_html(value)}">${frappe.utils.escape_html(__(value))}</span>`;
		},
		priority(value) {
			if (!value) return `<span class="text-muted">—</span>`;
			const color = { High: "red", Medium: "orange", Low: "gray" }[value] || "gray";
			return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(value))}</span>`;
		},
		due_date(value, df, doc) {
			if (!value) return `<span class="text-muted">—</span>`;
			const late = !["Done", "Cancelled"].includes(doc.status) && value < frappe.datetime.get_today();
			return `<span class="${late ? "text-danger" : ""}">${frappe.datetime.str_to_user(value)}</span>`;
		},
	},
};
