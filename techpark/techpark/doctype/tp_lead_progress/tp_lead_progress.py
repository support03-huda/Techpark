# Last edited: 2026-11-26
# Copyright (c) 2026, Techpark International
# 2026-11-26: dropdown master (client: every dropdown is a master)
from frappe.model.document import Document

from techpark.masters import DropdownMaster


class TPLeadProgress(DropdownMaster, Document):
	pass
