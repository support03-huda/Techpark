"""Turn the rows of every customer's Contacts tab into Customer Contact records (CON-0001 …)
and link each row to its record, so expenses and visits can point to the person met.

The tab's "Name" field was renamed name1 -> person_name; the old column is copied first.
"""

import frappe

FIELDS = ["person_name", "designation", "department", "phone", "email", "is_primary", "is_active", "notes"]


def execute():
	if frappe.db.has_column("Company contacts", "name1"):
		frappe.db.sql(
			"""update `tabCompany contacts` set person_name = name1
			where ifnull(person_name, '') = '' and ifnull(name1, '') != ''"""
		)

	rows = frappe.get_all(
		"Company contacts",
		filters={"parenttype": "TP Customer", "parentfield": "contacts", "record": ("is", "not set")},
		fields=["name", "parent", *FIELDS],
		order_by="parent asc, idx asc",
	)

	frappe.flags.tp_customer_sync = True  # the customer already holds the primary contact
	try:
		for row in rows:
			if not row.person_name or not frappe.db.exists("TP Customer", row.parent):
				continue
			try:
				contact = frappe.get_doc(
					{"doctype": "Customer Contact", "customer": row.parent, **{f: row.get(f) for f in FIELDS}}
				).insert(ignore_permissions=True)
			except frappe.ValidationError as e:
				# Leave the row unlinked; it is created (and the error shown) the next time the customer is saved
				frappe.clear_messages()
				print(f"Contact {row.person_name!r} of customer {row.parent} not migrated: {e}")
				continue
			frappe.db.set_value("Company contacts", row.name, "record", contact.name, update_modified=False)
	finally:
		frappe.flags.tp_customer_sync = False
