# Last edited: 2026-11-21
# Copyright (c) 2026, Techpark International
# 2026-11-21: Annual Demand = Principal share + up to 4 competitors; Machine = one Size field (client)
"""Move the old fixed share columns (N, Tyrolit, Asahi, TVMK, GNO, Cumi, Other) of every Technical Lead into
Principal Share + Competitor 1-4 (biggest first), and Size OD / T / ID into one Size. The old fields stay, hidden."""

import frappe
from frappe.utils import flt

OLD = [
	("share_noritake", "Noritake"),
	("share_tyrolit", "Tyrolit"),
	("share_asahi", "Asahi"),
	("share_tvmk", "TVMK"),
	("share_gno", "GNO"),
	("share_cumi", "Cumi"),
	("share_other", None),
]


def competitor(name):
	found = frappe.db.sql("select name from `tabTP Competitor` where lower(competitor_name) = lower(%s) limit 1", name)
	if found:
		return found[0][0]
	return frappe.get_doc({"doctype": "TP Competitor", "competitor_name": name, "is_active": 1}).insert(ignore_permissions=True).name


def execute():
	fields = ["name", "principal", "other_competitors", "size", "size_od", "size_t", "size_id", "principal_share", "competitor_1"]
	for doctype in ("TP Technical Lead", "TP Customer Technical Lead"):
		for r in frappe.get_all(doctype, fields=fields + [f for f, _l in OLD]):
			updates = {}
			if not r.size:
				size = " x ".join(str(x).strip() for x in (r.size_od, r.size_t, r.size_id) if x and str(x).strip())
				if size:
					updates["size"] = size
			if not flt(r.principal_share) and not r.competitor_1:
				principal = (r.principal or "").strip().lower()
				others = []
				for field, label in OLD:
					share = flt(r.get(field))
					if not share:
						continue
					if not label:
						text = (r.other_competitors or "").strip()
						label = text if text and "," not in text and len(text) <= 100 else "Other"
					if principal and (label.lower() == principal or label.lower() in principal):
						updates["principal_share"] = share
					else:
						others.append((share, label))
				for i, (share, label) in enumerate(sorted(others, key=lambda o: -o[0])[:4], start=1):
					updates[f"competitor_{i}"] = competitor(label)
					updates[f"competitor_{i}_share"] = share
			if updates:
				frappe.db.set_value(doctype, r.name, updates, update_modified=False)
