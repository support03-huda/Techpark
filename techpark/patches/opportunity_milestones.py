"""Fill the new Samples / Trials / Bulk Trials PO / Regularised columns of every opportunity from its visits."""

import frappe

from techpark.opportunity import refresh_opportunity


def execute():
	for name in frappe.get_all("TP Opportunity", pluck="name"):
		refresh_opportunity(name)
