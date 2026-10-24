# Copyright (c) 2026, Techpark International
"""Health check: run every TechPark report, dashboard chart and number card, and preview
the reminder digests, printing OK / FAIL for each. Nothing is changed or sent.

	bench --site techpark.local execute techpark.checks.run
	bench --site techpark.local execute techpark.checks.run --kwargs "{'user': 'someone@techpark.co.in'}"

With `user`, everything runs as that user, so a salesperson's restricted view is checked too.
"""

import frappe

MODULE = "TechPark"


def run(user=None):
	if user and not frappe.db.exists("User", user):
		print(f"No user {user!r} on this site. Pass a real login, e.g. a salesperson's email.")
		print("Users with Sales User:", ", ".join(sales_users()) or "none")
		return
	frappe.set_user(user or "Administrator")
	print(f"Running as {frappe.session.user}\n")
	failures = 0
	failures += check("Report", frappe.get_all("Report", filters={"module": MODULE}, pluck="name"), run_report)
	failures += check("Chart", frappe.get_all("Dashboard Chart", filters={"module": MODULE}, pluck="name"), run_chart)
	failures += check("Card", frappe.get_all("Number Card", filters={"module": MODULE}, pluck="name"), run_card)
	failures += check("Reminder", ["daily", "weekly", "quarterly"], run_reminder)
	print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed - see above.'}")
	frappe.db.rollback()


def sales_users():
	users = frappe.get_all("Has Role", filters={"parenttype": "User", "role": "Sales User"}, pluck="parent", distinct=True)
	return [u for u in users if u != "Administrator" and frappe.db.get_value("User", u, "enabled")]


def check(kind, names, runner):
	failures = 0
	for name in names:
		try:
			print(f"OK    {kind:<9} {name}: {runner(name)}")
		except Exception as e:
			failures += 1
			print(f"FAIL  {kind:<9} {name}: {type(e).__name__}: {e}")
	return failures


def run_report(name):
	from frappe.desk.query_report import run

	result = run(name, filters={})
	return f"{len(result.get('result') or [])} rows"


def run_chart(name):
	from frappe.desk.doctype.dashboard_chart.dashboard_chart import get

	chart = frappe.get_doc("Dashboard Chart", name)
	if chart.chart_type == "Report":
		# The desk draws these from the report's own chart.
		from frappe.desk.query_report import run

		data = (run(chart.report_name, filters=frappe.parse_json(chart.filters_json) or {}).get("chart") or {}).get("data") or {}
	else:
		data = get(chart_name=name, refresh=1) or {}
	values = sum(sum(v or 0 for v in d.get("values", [])) for d in data.get("datasets", []))
	return f"{len(data.get('labels') or [])} labels, total {values}"


def run_card(name):
	from frappe.desk.doctype.number_card.number_card import get_result

	doc = frappe.get_doc("Number Card", name)
	return get_result(doc.as_dict(), doc.filters_json or "[]")


def run_reminder(job):
	from techpark import reminders

	digests = getattr(reminders, job)(dry_run=True)
	return f"{len(digests)} recipient(s): " + (
		", ".join(f"{u} ({sum(len(r) for _t, _c, r in s)})" for u, s in digests.items()) or "nothing to send"
	)
