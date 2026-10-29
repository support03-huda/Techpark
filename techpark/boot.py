# Copyright (c) 2026, Techpark International
"""Desk boot: the Expense Approvals menu only for users who can approve expenses
(approvers, admins, and managers somebody reports to in TP Team Member).

Runs on every boot, after the cached part, so a change of Reports To shows on the next reload."""

from techpark.permission import can_approve_expenses

APPROVALS_PAGE = "tp-expense-approvals"


def extend_bootinfo(bootinfo):
	bootinfo.techpark_expense_approver = can_approve_expenses()
	if bootinfo.techpark_expense_approver:
		return
	for sidebar in (bootinfo.get("workspace_sidebar_item") or {}).values():
		sidebar["items"] = [item for item in sidebar.get("items", []) if item.get("link_to") != APPROVALS_PAGE]
