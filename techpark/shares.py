# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Annual Demand share = the lead's Principal + Competitor 1-4 (client; shown on the Technical Lead only)
"""Annual Demand share of a Technical Lead: Principal Share and Competitor 1-4 (TP Competitor)."""

import frappe
from frappe import _
from frappe.utils import flt

SLOTS = 4
FIELDS = ["principal_share"] + [f for i in range(1, SLOTS + 1) for f in (f"competitor_{i}", f"competitor_{i}_share")]


def competitor_names():
	"""{id: name} of every competitor (a small master), once per request."""
	if getattr(frappe.local, "tp_competitor_names", None) is None:
		frappe.local.tp_competitor_names = {
			str(c.name): c.competitor_name for c in frappe.get_all("TP Competitor", fields=["name", "competitor_name"])
		}
	return frappe.local.tp_competitor_names


def share_parts(row):
	"""["Noritake 40%", "Tyrolit 30%", ...], biggest first."""
	names = competitor_names()
	parts = []
	if flt(row.get("principal_share")):
		parts.append((flt(row.get("principal_share")), row.get("principal") or _("Principal")))
	for i in range(1, SLOTS + 1):
		competitor, share = row.get(f"competitor_{i}"), flt(row.get(f"competitor_{i}_share"))
		if competitor or share:
			parts.append((share, names.get(str(competitor), competitor) if competitor else _("Other")))
	return [f"{label} {round(share)}%" for share, label in sorted(parts, key=lambda p: -p[0])]


def validate_shares(doc):
	seen = set()
	for i in range(1, SLOTS + 1):
		competitor = doc.get(f"competitor_{i}")
		if competitor and str(competitor) in seen:
			frappe.throw(_("The same competitor is entered twice in Annual Demand."))
		seen.add(str(competitor))
	total = sum(flt(doc.get(f)) for f in FIELDS if f.endswith("share"))
	if total > 100:
		frappe.throw(_("Principal and competitor shares add up to {0}%: they cannot be more than 100%.").format(round(total, 1)))
