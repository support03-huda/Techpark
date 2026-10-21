# Copyright (c) 2026, Techpark International
"""Customer Turnover — code 601, 602 …; one record per customer, plant and financial year."""

import re

import frappe
from frappe import _
from frappe.model.document import Document

from techpark.naming import next_numeric_name

TURNOVER_CODE_START = 601


class CustomerTurnover(Document):
	def autoname(self):
		self.name = next_numeric_name(self.doctype, TURNOVER_CODE_START)

	def validate(self):
		self.financial_year = normalize_financial_year(self.financial_year)
		self.validate_duplicate()

	def validate_duplicate(self):
		duplicate = frappe.db.get_value(
			self.doctype,
			{
				"customer": self.customer,
				"plant": self.plant or ("is", "not set"),
				"financial_year": self.financial_year,
				"name": ("!=", self.name or ""),
			},
		)
		if duplicate:
			frappe.throw(
				_("Turnover for {0}{1} is already recorded in {2}.").format(
					frappe.bold(self.financial_year),
					_(" at plant {0}").format(frappe.bold(self.plant)) if self.plant else "",
					frappe.bold(duplicate),
				)
			)


def normalize_financial_year(value):
	"""'2025-26', '2025/2026', '2025 - 2026' -> '2025-2026'."""
	value = (value or "").strip()
	match = re.fullmatch(r"(\d{4})\s*[-/]\s*(\d{2}|\d{4})", value)
	if not match:
		frappe.throw(_("Financial Year must look like 2025-2026."))
	start, end = int(match.group(1)), match.group(2)
	# 2-digit end year: 2099-00 is 2099-2100
	end = int(end) if len(end) == 4 else (start + 1 if (start + 1) % 100 == int(end) else None)
	if end != start + 1:
		frappe.throw(_("Financial Year {0} must span two consecutive years, e.g. 2025-2026.").format(value))
	return f"{start}-{end}"
