"""One customer = one site: the Plant is hidden, so the customer shows the address and GST details
(taken from its plant where the customer has none), and records without a plant get the customer's."""

import frappe

from techpark.customer_sync import default_plant

FIELDS = {
	"customer_address": "plant_address",
	"plant_location": "plant_location",
	"state": "state",
	"pincode": "pincode",
	"gstin": "gstin",
	"gst_registration_type": "gst_registration_type",
}
PLANT_FIELD = {
	"Customer Product Production": "plant",
	"Customer Turnover": "plant",
	"Customer Segment Application": "address",
	"Wheel Specification": "plant",
	"Wheel Consumption": "plant",
	"Manufacturing Details": "plant",
	"Daily Visit Report": "plant",
}


def execute():
	for customer in frappe.get_all("TP Customer", fields=["name", *FIELDS]):
		plant = default_plant(customer.name)
		if not plant:
			continue
		values = frappe.db.get_value("Plant", plant, list(set(FIELDS.values())), as_dict=True)
		missing = {f: values[p] for f, p in FIELDS.items() if not customer[f] and values[p]}
		if missing:
			frappe.db.set_value("TP Customer", customer.name, missing, update_modified=False)

		for doctype, field in PLANT_FIELD.items():
			frappe.db.sql(
				f"update `tab{doctype}` set `{field}` = %s where customer = %s and ifnull(`{field}`, '') = ''",
				(plant, customer.name),
			)
	frappe.db.sql(
		"""update `tabDaily Visit Report` dvr join `tabPlant` p on p.name = dvr.plant
		set dvr.plant_name = p.plant_name where ifnull(dvr.plant_name, '') = ''"""
	)
