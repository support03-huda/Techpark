# Copyright (c) 2026, Techpark International
"""Territory / Region — sales territory on a customer (West - MH, East - WB, …), grouped by zone."""

from frappe.model.document import Document


class TerritoryRegion(Document):
	def validate(self):
		self.region_name = (self.region_name or "").strip()
