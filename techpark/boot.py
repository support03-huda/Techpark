# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
"""Desk boot: the Expense Approvals menu only for users who can approve expenses
(approvers, admins, and managers somebody reports to in TP Team Member).

Runs on every boot, after the cached part, so a change of Reports To shows on the next reload."""

from techpark.permission import can_approve_expenses

APPROVALS_PAGE = "tp-expense-approvals"


def extend_bootinfo(bootinfo):
	from techpark.roles import for_boot

	bootinfo.techpark_roles = for_boot()  # 2026-11-26: TechPark Settings > Roles for the desk scripts
	# 2026-11-27: master values by App Key (they can be renamed) and their colours, for the desk scripts
	from techpark.masters import colours, keys_for_boot

	bootinfo.techpark_keys = keys_for_boot()
	bootinfo.techpark_colours = colours()
	from techpark.masters import ID_PREFIX

	bootinfo.techpark_masters = list(ID_PREFIX)  # 2026-11-27: their list shows the ID (DVS-0001), not the name as ID
	from techpark.statuses import status_rows

	from techpark.statuses import default_lead_progress

	# 2026-11-27: a new Technical Lead shows its Progress (TP Lead Progress > Default) and Stage (Development) at once
	bootinfo.techpark_default_lead_progress = default_lead_progress()
	bootinfo.techpark_status_results = {r.name: r.result for r in status_rows()}  # 2026-11-27: status colours
	bootinfo.techpark_expense_approver = can_approve_expenses()
	if bootinfo.techpark_expense_approver:
		return
	for sidebar in (bootinfo.get("workspace_sidebar_item") or {}).values():
		sidebar["items"] = [item for item in sidebar.get("items", []) if item.get("link_to") != APPROVALS_PAGE]
