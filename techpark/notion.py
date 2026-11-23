# Last edited: 2026-11-22
# Copyright (c) 2026, Techpark International
# 2026-11-22: an opportunity "Sent to Principal" is pushed to the principal's Notion database (client)
"""Push to a principal's Notion database (e.g. Noritake's "TECHPARK Negotiation List").

Set up on the Principal: Push to Notion, the Notion Database ID and the Internal Integration Secret
(made by the workspace owner at notion.so/my-integrations and connected to that database).

When an opportunity of that principal reaches "Sent to Principal", one page is created in the database
(once; the page link is kept on the opportunity). Only properties that exist in the database, with a
matching type, are filled — so a renamed or removed column never breaks the push.
"""

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime, today

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TRIGGER_STATUS = "Sent to Principal"
# columns filled (matched by the start of the Notion column name, any case)
KEYS = ("importance", "agency", "beginning of negotiations", "business negotiation details", "product classification", "grinding method", "target process", "customer requests")


def _config(principal):
	p = frappe.db.get_value("Principal", principal, ["notion_enabled", "notion_database_id"], as_dict=True)
	if not p or not p.notion_enabled or not p.notion_database_id:
		return None
	token = frappe.get_doc("Principal", principal).get_password("notion_token", raise_exception=False)
	if not token:
		return None
	return frappe._dict(token=token, database=_database_id(p.notion_database_id))


def _database_id(value):
	"""Accepts the ID or the whole database link."""
	value = (value or "").strip().split("?")[0].rstrip("/")
	return value.split("/")[-1].split("-")[-1] if "/" in value or len(value) > 36 else value


def _call(method, path, token, body=None):
	r = requests.request(
		method,
		API + path,
		json=body,
		headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"},
		timeout=30,
	)
	data = r.json() if r.content else {}
	if r.status_code >= 400:
		raise frappe.ValidationError(_("Notion: {0}").format(data.get("message") or r.status_code))
	return data


def _properties(cfg):
	"""{lower-case name: (real name, type)} of the database's columns."""
	db = _call("GET", f"/databases/{cfg.database}", cfg.token)
	return {name.strip().lower(): (name, prop["type"]) for name, prop in db.get("properties", {}).items()}


def _value(ptype, value):
	value = str(value).strip()
	if not value:
		return None
	if ptype in ("title", "rich_text"):
		return [{"type": "text", "text": {"content": value[:2000]}}]
	if ptype == "select":
		return {"name": value.replace(",", " ")[:100]}
	if ptype == "multi_select":
		return [{"name": value.replace(",", " ")[:100]}]
	if ptype == "date":
		return {"start": value[:10]}
	if ptype == "url":
		return value
	return None


def _page_values(opp):
	"""Column name (as in their Notion list) -> value. Matched by the start of the name, any case."""
	lead = frappe.db.get_value(
		"TP Technical Lead",
		{"customer": opp.customer, "principal": opp.principal, "application": opp.application},
		["application_master", "grinding_process"],
		as_dict=True,
	) or frappe._dict()
	segment = frappe.db.get_value("Customer Application", lead.application_master, "industry_domain") if lead.application_master else None
	details = "\n".join(
		x
		for x in (
			opp.present_status,
			_("Spec: {0}").format(opp.spec) if opp.spec else "",
			_("Size: {0}").format(opp.size) if opp.size else "",
		)
		if x
	)
	return {
		"__title__": f"{opp.customer_name or opp.customer} : {opp.application or ''}".strip(" :"),
		"importance": opp.importance,
		"agency": "TECHPARK",
		"beginning of negotiations": opp.first_visit or today(),
		"business negotiation details": details,
		"product classification": segment,
		"grinding method": lead.grinding_process,
		"target process": opp.application,
		"customer requests": opp.next_action,
	}


def push_opportunity(name):
	"""Create the opportunity's page in its principal's Notion database (once)."""
	opp = frappe.get_doc("TP Opportunity", name)
	if opp.get("notion_page_url"):
		return
	cfg = _config(opp.principal)
	if not cfg:
		return
	try:
		props = _properties(cfg)
		body = {}
		for key, value in _page_values(opp).items():
			if value in (None, ""):
				continue
			if key == "__title__":
				match = next(((n, t) for n, t in props.values() if t == "title"), None)
			else:
				match = next(((n, t) for low, (n, t) in props.items() if low.startswith(key)), None)
			if not match:
				continue
			v = _value(match[1], value)
			if v is not None:
				body[match[0]] = {match[1]: v}
		page = _call("POST", "/pages", cfg.token, {"parent": {"database_id": cfg.database}, "properties": body})
		frappe.db.set_value(
			"TP Opportunity", name, {"notion_page_url": page.get("url"), "notion_pushed_on": now_datetime()}, update_modified=False
		)
		opp.add_comment("Info", _("Sent to {0}'s Notion: {1}").format(opp.principal, page.get("url")))
	except Exception:
		frappe.log_error(title=_("Notion push failed: {0}").format(name))
		opp.add_comment("Info", _("Could not send to {0}'s Notion (see Error Log).").format(opp.principal))


def on_opportunity_refresh(doc):
	"""Called after an opportunity is refreshed from its visits."""
	if doc.status != TRIGGER_STATUS or doc.get("notion_page_url"):
		return
	if not frappe.db.get_value("Principal", doc.principal, "notion_enabled"):
		return
	frappe.enqueue("techpark.notion.push_opportunity", name=doc.name, enqueue_after_commit=True)


@frappe.whitelist()
def test_connection(principal):
	"""The database's columns and which of them TechPark fills."""
	frappe.only_for(("System Manager", "TechPark Approver"))
	cfg = _config(principal)
	if not cfg:
		frappe.throw(_("Tick Push to Notion and fill the Database ID and the Integration Secret first."))
	props = _properties(cfg)
	keys = KEYS
	filled = [n for low, (n, t) in props.items() if t == "title" or any(low.startswith(k) for k in keys)]
	return {"columns": sorted(n for n, t in props.values()), "filled": sorted(filled)}


# 2026-11-22: make the Negotiation List table in Notion from TechPark (the token never leaves the server)
COLUMNS = {
	"Opportunity name": {"title": {}},
	"Importance": {"select": {"options": [{"name": "High", "color": "red"}, {"name": "Medium", "color": "yellow"}, {"name": "Low", "color": "gray"}]}},
	"Agency": {"select": {"options": [{"name": "TECHPARK", "color": "red"}]}},
	"beginning of negotiations": {"date": {}},
	"Business negotiation details": {"rich_text": {}},
	"Product classification": {"select": {}},
	"Grinding method": {"rich_text": {}},
	"Target process": {"rich_text": {}},
	"Customer requests": {"rich_text": {}},
}


@frappe.whitelist()
def create_database(principal, page):
	"""Create the table inside a Notion page (shared with the connection) and save its ID on the principal."""
	frappe.only_for(("System Manager", "TechPark Approver"))
	doc = frappe.get_doc("Principal", principal)
	token = doc.get_password("notion_token", raise_exception=False)
	if not token:
		frappe.throw(_("Save the Notion Integration Secret first."))
	db = _call(
		"POST",
		"/databases",
		token,
		{
			"parent": {"type": "page_id", "page_id": _database_id(page)},
			"title": [{"type": "text", "text": {"content": f"TECHPARK Negotiation List ({principal})"}}],
			"properties": COLUMNS,
		},
	)
	frappe.db.set_value("Principal", principal, {"notion_enabled": 1, "notion_database_id": db["id"]})
	return db.get("url")

