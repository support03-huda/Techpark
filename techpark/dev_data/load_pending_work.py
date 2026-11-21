# Last edited: 2026-11-14
# Copyright (c) 2026, Techpark International
"""Load the "TP Pending Work" tab of their Teams sheet as Pending Work records, exactly as written
there (one record per filled cell, the column as its Category). Nothing else is filled in.

	bench --site techpark.local execute techpark.dev_data.load_pending_work.execute

Responsible = the user running it (the sheet has no names). Safe to run again: a row already
loaded (same category + text) is skipped, and anything not in the sheet is removed (dev only!).
"""

import frappe

ROWS = {
	"SO's": [
		"Schaeffler : PO#52665866",
		"SKF : PO#490345",
	],
	"OC's to make": [
		"SKF Haridwar : PO#...52x13x14-100 pcs",
		"NRB-W : PO#6220001607_May need to change",
		"SKF : PO#490343, 46,54, 60",
	],
	"Routine monthly work": [
		"1. Stock checking and match",
		"2. Pend. Pay list - 1st of Month",
		"** Plastic packing material list",
	],
	"Desp. / invoices (Techpark)": [
		"TATA Kgp : Stone cutting / Desp.",
		"Cummins / Kalika - Pay / Desp.",
		"Gajara Differential : PI for all",
		"Gajara : Desp.",
		"KCI : Stone cutting - Desp.",
		"Texspin P1 :",
		"Samples : Bosch , Synnova",
		"SKF Pune :",
	],
	"Despatches (Direct)": [
		"SKF : N-F07067_SEA",
		"NHB : N-F07072_SEA_23.3K",
		"TATA : N-F07073_SEA",
		"BFL-B : N-F07077_SEA_0.223",
		"BFL-P : N-F07078_SEA_0.67",
		"TATA : N-F07080_SEA_0.968",
		"SKF: N-F07090_SEA_1.27",
		"SKF: N-F07091_AIR_0.3_4.9.-",
		"NIPRO : N-F07096",
		"TP: N-F07098_SEA_2.09_9.9-",
		"TP: N-F07097_AIR_1.91_4.9.26-6.9.26",
		"TP: N-F07086_SEA_2.37_2.9-24.9",
		"TP: N-F07074_SEA_26.8-17.9",
		"TP: N-F07064_SEA_19.8-27.8_17.9",
		"TP: N-F07059_SEA_1.494_20.8_10.9",
		"TP: N-F07054_SEA_11.8.26",
		"TP: N-F07044_SEA_29.7-31.7-20.8.-2.9.26",
	],
	"Others": [
		"Milind : Website",
		"DVR for Customer data management",
		"2 laptops ( 1 old + 1 for battery change) to get back from Milind",
		"*Fire NOC / Valid License /",
		"* Employees Health & Safety.",
		"( Physical work , sanitation , food )",
		"Factory / Warehouse acts ?",
		"* Instruction of handling/ storage/ Usage..",
	],
}


def execute(responsible=None):
	responsible = responsible or frappe.session.user
	# an earlier load used other category names / wording: remove what is not in the sheet
	wanted = {(c, t) for c, tasks in ROWS.items() for t in tasks}
	removed = 0
	for w in frappe.get_all("TP Pending Work", fields=["name", "category", "task"]):
		if (w.category, w.task) not in wanted:
			frappe.delete_doc("TP Pending Work", w.name, ignore_permissions=True)
			removed += 1
	made = skipped = 0
	for category, tasks in ROWS.items():
		for task in tasks:
			if frappe.db.exists("TP Pending Work", {"category": category, "task": task}):
				skipped += 1
				continue
			frappe.get_doc(
				{
					"doctype": "TP Pending Work",
					"category": category,
					"task": task,
					"responsible": [{"user": responsible}],
				}
			).insert()
			made += 1
	frappe.db.commit()
	print(f"Pending Work: {removed} removed (not in the sheet), {made} created, {skipped} already there.")
