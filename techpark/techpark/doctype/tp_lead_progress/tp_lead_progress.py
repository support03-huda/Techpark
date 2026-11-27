# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
# 2026-11-26: dropdown master (client: every dropdown is a master)
import frappe
from frappe.model.document import Document

from techpark.masters import DropdownMaster


class TPLeadProgress(DropdownMaster, Document):
	def on_update(self):
		super().on_update()  # 2026-11-27: DropdownMaster
		# 2026-11-27: one Default (a new Technical Lead's Progress)
		if self.is_default:
			frappe.db.set_value("TP Lead Progress", {"is_default": 1, "name": ("!=", self.name)}, "is_default", 0)
