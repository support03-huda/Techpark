// Last edited: 2026-11-12
// Copyright (c) 2026, Techpark International
// Development Board: application lines in the Development stage. The board itself is in public/js/tp_board.js.

{% include "techpark/public/js/tp_board.js" %}

frappe.pages["techpark-development-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Development Board"), single_column: true });
	wrapper.tp_board = new TPBoard(page, "Development");
};

frappe.pages["techpark-development-board"].on_page_show = function (wrapper) {
	if (wrapper.tp_board && wrapper.tp_board.loaded) wrapper.tp_board.refresh();
};
