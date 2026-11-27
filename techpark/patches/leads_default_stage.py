# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-27 (client): a lead starts in Development; the older leads without a Stage (not visited yet) get it too
import frappe

from techpark.masters import STAGE, K, clear_keys


def execute():
	clear_keys()
	stage = K(STAGE, "Development")
	if not frappe.db.exists("TP Stage", stage):
		return
	names = frappe.get_all("TP Technical Lead", filters={"stage": ("is", "not set")}, pluck="name")
	for name in names:
		frappe.db.set_value("TP Technical Lead", name, "stage", stage, update_modified=False)
	if names:
		frappe.db.sql(
			"""update `tabTP Customer Technical Lead` set stage = %s
			where ifnull(stage, '') = '' and record in %s""",
			(stage, tuple(names)),
		)
