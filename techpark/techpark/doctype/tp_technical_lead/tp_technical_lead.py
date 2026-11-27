# Last edited: 2026-11-27
# Copyright (c) 2026, Techpark International
"""One application of a customer (Demand Survey row). Filled once, then picked on visits."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from techpark.shares import validate_shares


# 2026-11-26: the lead's main fields; a change is only noted on its timeline (no freeze for now, client)
FROZEN = ("principal", "product", "application_master", "production_line", "supplier_product_category", "size")


@frappe.whitelist()
def set_frozen(name, frozen):
	"""2026-11-27: Freeze: anybody who may edit the lead; Unfreeze: admins only (TechPark Settings > Admin Roles)."""
	from techpark.permission import is_manager

	frozen = frappe.utils.cint(frozen)
	doc = frappe.get_doc("TP Technical Lead", name)
	if frozen:
		if not frappe.has_permission("TP Technical Lead", "write", doc):
			frappe.throw(_("You may not freeze {0}.").format(name), frappe.PermissionError)
	elif not is_manager():
		frappe.throw(_("Only an admin can unfreeze a Technical Lead."), frappe.PermissionError)
	doc.db_set(
		{"is_frozen": frozen, "frozen_by": frappe.session.user if frozen else None, "frozen_on": now_datetime() if frozen else None},
		notify=True,
	)
	# 2026-11-27: the customer's Technical Leads tab row shows it too (its Freeze / Unfreeze button reads it)
	frappe.db.set_value("TP Customer Technical Lead", {"record": name}, "is_frozen", frozen, update_modified=False)
	doc.add_comment("Info", _("Frozen: no changes until an admin unfreezes it.") if frozen else _("Unfrozen."))
	return frozen


class TPTechnicalLead(Document):
	# 2026-11-26: leads can be made by hand (form / customer tab) and from a DVR (client: keep it flexible);
	# check_duplicate stops a second lead for the same application + production line either way.
	def onload(self):
		# 2026-11-27: the Freeze / Unfreeze button shows for admins (decided here, not in the browser)
		from techpark.permission import is_manager

		# 2026-11-27: Freeze for whoever may edit it, Unfreeze for admins
		self.set_onload("can_freeze", bool(frappe.has_permission("TP Technical Lead", "write", self)))
		self.set_onload("can_unfreeze", is_manager())

	def before_insert(self):
		self.lead_created_on = now_datetime()  # 2026-11-26: when the lead was made (client)
		if not self.progress:
			from techpark.statuses import default_lead_progress

			self.progress = default_lead_progress()  # 2026-11-27: To Start (TP Lead Progress > Default)
		if not self.stage:
			from techpark.masters import STAGE, K

			self.stage = K(STAGE, "Development")  # 2026-11-27 (client): a new lead starts in Development

	def validate(self):
		self.check_freeze()  # 2026-11-27
		self.check_duplicate()  # 2026-11-26
		self.check_frozen()  # 2026-11-26
		self.set_progress_effect()  # 2026-11-26
		if self.application_master:
			# Common application list: the name (and defaults) come from the master
			master = frappe.db.get_value(
				"Customer Application", self.application_master, ["application_name", "grinding_process", "product"],
				as_dict=True,
			)
			if master:
				self.application = master.application_name
				self.grinding_process = master.grinding_process
				self.product = self.product or master.product
				# 2026-11-21: category / line no longer on the Application master (client)
		validate_shares(self)  # 2026-11-21: Principal + 4 competitors, max 100%
		self.application = cstr(self.application).strip()
		if not self.application:
			frappe.throw(_("Pick the Application."))
		if self.supplier_product_category and self.principal:
			principal = frappe.db.get_value("Supplier Product Category", self.supplier_product_category, "principal")
			if principal and principal != self.principal:
				frappe.throw(_("Principal Product Category {0} belongs to {1}, not {2}.").format(
					frappe.bold(self.supplier_product_category), principal, self.principal
				))

	def check_frozen(self):
		"""2026-11-26: a change to Principal, Product, Application, Production Line, Category or Size of a saved lead
		is allowed once the user confirmed it on the form ("Do you want to save?", lead form / customer tab);
		it is noted on the lead's timeline, since earlier visits were made with the old values."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = [f for f in FROZEN if cstr(before.get(f)).strip() != cstr(self.get(f)).strip()]
		if changed:
			self.add_comment(
				"Info",
				_("Changed: {0}").format(
					", ".join(f"{_(self.meta.get_label(f))}: {before.get(f) or '-'} → {self.get(f) or '-'}" for f in changed)
				),
			)

	def set_progress_effect(self):
		"""2026-11-26: the Lead Progress master decides: Moves Lead to Stage (Regularised -> Sales), Closes the Lead
		(Evaluation Failed: not offered on visits, off the boards)."""
		from techpark.statuses import progress_effect

		effect = progress_effect(self.progress)
		self.is_closed = 1 if effect.closes_lead else 0
		if effect.moves_to_stage:
			self.stage = effect.moves_to_stage

	def on_update(self):
		self.update_visits()  # 2026-11-26
		# 2026-11-26: its development line (board) follows a new progress
		if self.opportunity and self.has_value_changed("progress"):
			from techpark.opportunity import refresh_opportunity

			refresh_opportunity(self.opportunity)

	def update_visits(self):
		"""2026-11-26: the change (confirmed on the form: "this will affect N visits") goes to the lead's visits."""
		before = self.get_doc_before_save()
		if not before:
			return
		from techpark.application import LEAD_TO_VISIT, update_lead_visits

		changed = [f for f in LEAD_TO_VISIT if cstr(before.get(f)).strip() != cstr(self.get(f)).strip()]
		if not changed:
			return
		count = update_lead_visits(self, changed)
		if count:
			self.add_comment("Info", _("{0} visit(s) updated with the changed lead data.").format(count))

	def on_trash(self):
		if self.is_frozen:  # 2026-11-27
			frappe.throw(_("Technical Lead {0} is frozen: an admin must Unfreeze it before it can be deleted.").format(frappe.bold(self.name)))

	def check_freeze(self):
		"""2026-11-27: a frozen lead cannot be changed by anybody, admins too: an admin first presses Unfreeze
		(then Freeze again). Freeze / Unfreeze go through set_frozen (admins only), not through a save."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if before and (before.is_frozen or self.is_frozen != before.is_frozen):
			frappe.throw(
				_("Technical Lead {0} is frozen: an admin must Unfreeze it before it can be changed.").format(frappe.bold(self.name))
			)  # a plain validation error, so the customer tab shows "Technical Leads row #n: ..."

	def check_duplicate(self):
		"""2026-11-26: one Technical Lead per customer + principal + application + production line
		(one application can run on several lines: Ch-1, Ch-2 ...)."""
		if not (self.customer and self.principal and self.application_master):
			return
		other = frappe.db.sql(
			"""select name from `tabTP Technical Lead`
			where customer = %s and principal = %s and application_master = %s
				and lower(trim(ifnull(production_line, ''))) = %s and ifnull(product, '') = %s and name != %s limit 1""",
			(
				self.customer, self.principal, self.application_master,
				cstr(self.production_line).strip().lower(), cstr(self.product), self.name or "",
			),  # 2026-11-26: Product is part of the lead too
		)
		if other:
			frappe.throw(
				_("This customer already has this Technical Lead (same application, product and production line): {0}. Open it, or make a DVR for it.").format(
					frappe.get_desk_link("TP Technical Lead", other[0][0])
				),
				frappe.DuplicateEntryError,
			)
