# Copyright (c) 2026, Techpark International
"""Visiting card scan: read a card photo with OpenAI and return the details for the TP Customer form."""

import base64
import json
import mimetypes

import frappe
import requests
from frappe import _

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")

CARD_FIELDS = {
	"company_name": "Company / organisation name, as printed",
	"person_name": "Full name of the person",
	"designation": "Job title / designation",
	"department": "Department, if printed",
	"phones": "Every phone / mobile number, each with country code if printed",
	"email": "Email address of the person (or the company email if only that is printed)",
	"website": "Website",
	"address": "Postal address without city, state and pincode",
	"city": "City / town",
	"state": "Indian state, full name (e.g. Maharashtra)",
	"pincode": "6-digit PIN code",
	"gstin": "15-character GSTIN, if printed",
}

PROMPT = (
	"These are photos of a business visiting card (front, and the back if given), usually from an Indian company. "
	"Combine the details from both sides. "
	"Read it and return the details. Copy text exactly as printed; fix only obvious OCR mistakes. "
	"Use an empty string (or an empty list) for anything not on the card. Do not guess."
)


def card_schema():
	properties = {
		field: {"type": "array", "items": {"type": "string"}, "description": text}
		if field == "phones"
		else {"type": "string", "description": text}
		for field, text in CARD_FIELDS.items()
	}
	return {
		"type": "object",
		"properties": properties,
		"required": list(CARD_FIELDS),
		"additionalProperties": False,
	}


def image_part(file_url):
	"""The image at file_url as an OpenAI message part."""
	file = frappe.get_doc("File", {"file_url": file_url})
	file.check_permission("read")
	mime = mimetypes.guess_type(file.file_name or file_url)[0]
	if mime not in IMAGE_TYPES:
		frappe.throw(_("Upload the visiting card as a JPG, PNG or WEBP image."))
	image = base64.b64encode(file.get_content()).decode()
	return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image}", "detail": "high"}}


@frappe.whitelist()
def scan_card(file_url, back_url=None):
	"""Details read from the visiting card: front image at file_url, back (if any) at back_url."""
	if not (frappe.has_permission("TP Customer", "write") or frappe.has_permission("TP Customer", "create")):
		frappe.throw(_("Not permitted to scan visiting cards."), frappe.PermissionError)

	settings = frappe.get_single("TechPark Settings")
	api_key = settings.get_password("openai_api_key", raise_exception=False)
	if not api_key:
		frappe.throw(_("Set the OpenAI API Key in TechPark Settings to scan visiting cards."))

	images = [image_part(url) for url in (file_url, back_url) if url]

	payload = {
		"model": settings.openai_model or DEFAULT_MODEL,
		"messages": [
			{
				"role": "user",
				"content": [{"type": "text", "text": PROMPT}, *images],
			}
		],
		"response_format": {
			"type": "json_schema",
			"json_schema": {"name": "visiting_card", "strict": True, "schema": card_schema()},
		},
	}
	try:
		response = requests.post(
			OPENAI_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=90
		)
	except requests.RequestException:
		frappe.log_error("Visiting card scan failed")
		frappe.throw(_("Could not reach OpenAI. Please try again."))

	if response.status_code != 200:
		frappe.log_error("Visiting card scan failed", response.text)
		messages = {
			401: _("The OpenAI API Key in TechPark Settings is not valid."),
			429: _("OpenAI limit or credit exhausted. Please check the OpenAI account."),
		}
		frappe.throw(messages.get(response.status_code) or _("OpenAI could not read the card."))

	card = json.loads(response.json()["choices"][0]["message"]["content"])
	card["phones"] = [p.strip() for p in card.get("phones") or [] if p.strip()]
	return {k: (v.strip() if isinstance(v, str) else v) for k, v in card.items()}
