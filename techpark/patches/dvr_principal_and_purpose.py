"""DVR spec update: create the Principals, move existing visits to the approved
Visit Purpose options (Routine / Trial / Issue / Commercial / Stock) and stamp
the fixed distributor "TP"."""

import frappe

from techpark.install import seed_principals

PURPOSE_MAP = {
	"Introduction": "Routine",
	"Relationship Visit": "Routine",
	"Technical Discussion": "Routine",
	"Trial / Demo": "Trial",
	"Complaint / Service": "Issue",
	"Received Enquiry": "Commercial",
	"Enquiry Follow-up": "Commercial",
	"Quotation Follow-up": "Commercial",
	"Order Follow-up": "Commercial",
	"Payment Follow-up": "Commercial",
}


def execute():
	seed_principals()

	for doctype in ("Daily Visit Report", "TP Customer Visit"):
		for old, new in PURPOSE_MAP.items():
			frappe.db.set_value(doctype, {"visit_purpose": old}, "visit_purpose", new, update_modified=False)

	frappe.db.set_value(
		"Daily Visit Report", {"distributor": ("is", "not set")}, "distributor", "TP", update_modified=False
	)
