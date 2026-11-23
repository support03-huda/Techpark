// Last edited: 2026-11-22
// Copyright (c) 2026, Techpark International
// 2026-11-22: check the Notion connection of a principal
frappe.ui.form.on("Principal", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.notion_enabled) return;
		// 2026-11-22: create the table in a Notion page shared with the connection
		frm.add_custom_button(__("Create Notion Table"), () =>
			frappe.prompt(
				{ fieldname: "page", fieldtype: "Data", reqd: 1, label: __("Notion page link") },
				(v) =>
					frappe.call({ method: "techpark.notion.create_database", args: { principal: frm.doc.name, page: v.page }, freeze: true }).then((r) => {
						frm.reload_doc();
						frappe.msgprint({ title: __("Notion table created"), indicator: "green", message: `<a href="${r.message}" target="_blank">${__("Open in Notion")}</a>` });
					}),
				__("Create Notion Table"),
				__("Create")
			)
		);
		frm.add_custom_button(__("Test Notion"), () =>
			frappe.call({ method: "techpark.notion.test_connection", args: { principal: frm.doc.name }, freeze: true }).then((r) => {
				const m = r.message || {};
				const esc = frappe.utils.escape_html;
				frappe.msgprint({
					title: __("Notion connected"),
					indicator: "green",
					message: `<p>${__("Filled by TechPark")}: <b>${(m.filled || []).map(esc).join(", ") || "-"}</b></p><p class="text-muted small">${__("All columns")}: ${(m.columns || []).map(esc).join(", ")}</p>`,
				});
			})
		);
	},
});
