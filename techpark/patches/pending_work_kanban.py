# Copyright (c) 2026, Techpark International
"""Pending Work as a board with the columns of their Teams sheet (Category)."""

import frappe

BOARD = "Pending Work"


def execute():
	if frappe.db.exists("Kanban Board", BOARD):
		return
	options = [o for o in (frappe.get_meta("TP Pending Work").get_field("category").options or "").split("\n") if o]
	board = frappe.get_doc(
		{
			"doctype": "Kanban Board",
			"kanban_board_name": BOARD,
			"reference_doctype": "TP Pending Work",
			"field_name": "category",
			"private": 0,
			"show_labels": 0,
			"columns": [{"column_name": o, "status": "Active", "indicator": "Gray"} for o in options],
			"filters": '[["TP Pending Work","status","in",["Open","In Progress"]]]',
		}
	)
	board.insert(ignore_permissions=True)
