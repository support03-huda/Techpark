# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Process is a master (client): Internal Grinding, Cylindrical Grinding, …
"""Grinding process of an application (Applications master)."""

from frappe.model.document import Document


class Process(Document):
	def validate(self):
		self.process_name = (self.process_name or "").strip()
