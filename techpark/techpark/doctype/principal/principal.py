# Copyright (c) 2026, Techpark International
"""Principal — the brands TechPark distributes for (Noritake, Everloy, ALMT)."""

from frappe.model.document import Document


class Principal(Document):
	def validate(self):
		self.principal_name = (self.principal_name or "").strip()
