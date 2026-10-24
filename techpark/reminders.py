# Copyright (c) 2026, Techpark International
"""Reminder digests, sent as a bell notification and an email (from the site's outgoing
account) to each salesperson and manager. Limits come from TechPark Settings.

Daily     - follow-ups overdue by N days, escalated to the managers.
Weekly    - prospects gone cold, customers not visited, pending actions by principal.
Quarterly - customer data still missing (contact, plant, industry, turnover …).

Each person gets one message per run listing only their own customers (managers: all).
To see what would be sent without sending: bench --site <site> execute techpark.reminders.preview
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, escape_html, formatdate, get_fullname, getdate, today

from techpark.techpark.doctype.techpark_settings.techpark_settings import get_setting

MANAGER_ROLES = ("Sales Manager", "TechPark Approver")


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------


def daily(dry_run=False):
	digests = defaultdict(list)
	escalate_follow_ups(digests)
	return deliver(digests, _("TechPark: overdue follow-ups need attention"), "/app/todo?status=Open", dry_run)


def weekly(dry_run=False):
	digests = defaultdict(list)
	cold_prospects(digests)
	not_visited(digests)
	pending_actions(digests)
	return deliver(
		digests, _("TechPark weekly reminders: customers and pending actions"),
		"/app/query-report/Application Development Status", dry_run,
	)


def quarterly(dry_run=False):
	digests = defaultdict(list)
	missing_customer_data(digests)
	return deliver(digests, _("TechPark: customer data pending this quarter"), "/app/tp-customer", dry_run)


def preview(job="weekly"):
	"""Print who would get what, without sending anything."""
	result = {"daily": daily, "weekly": weekly, "quarterly": quarterly}[job](dry_run=True)
	for user, sections in result.items():
		print(user, {title: len(rows) for title, _cols, rows in sections})
	if not result:
		print("Nothing to send.")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def escalate_follow_ups(digests):
	days = get_setting("follow_up_escalation_days")
	rows = [r for r in open_follow_ups() if r.due and date_diff(today(), r.due) >= days]
	if not rows:
		return
	cols = [_("Salesperson"), _("Customer"), _("Principal"), _("Next Action"), _("Due"), _("Days Overdue"), _("Visit")]
	table = [
		[r.salesperson_name, r.customer_name, r.principal, r.action, formatdate(r.due), date_diff(today(), r.due), link("daily-visit-report", r.dvr)]
		for r in sorted(rows, key=lambda r: r.due)
	]
	add(digests, get_managers(), _("Follow-ups overdue by {0}+ days").format(days), cols, table)


def cold_prospects(digests):
	days = get_setting("prospect_cold_days")
	customer_section(
		digests, "Prospect", days, _("Prospects gone cold (no visit for {0}+ days)").format(days)
	)


def not_visited(digests):
	days = get_setting("not_visited_days")
	customer_section(
		digests, "Active Customer", days, _("Customers not visited for {0}+ days").format(days)
	)


def customer_section(digests, status, days, title):
	last_visits = get_last_visits()
	agents = get_agents()
	cutoff = add_days(today(), -days)
	cols = [_("Customer"), _("Region"), _("Last Visit"), _("Days"), _("Handled By")]
	per_user = defaultdict(list)
	everything = []
	for c in frappe.get_all(
		"TP Customer",
		filters={"customer_status": status},
		fields=["name", "customer_name", "territory_region", "creation", "prospect_since"],
		order_by="customer_name",
	):
		last = last_visits.get(c.name)
		since = last or c.prospect_since or getdate(c.creation)
		if getdate(since) > getdate(cutoff):
			continue
		handlers = agents.get(c.name, [])
		row = [
			link("tp-customer", c.name, c.customer_name),
			c.territory_region,
			formatdate(last) if last else _("Never"),
			date_diff(today(), since),
			", ".join(get_fullname(u) for u in handlers) or _("Not assigned"),
		]
		everything.append(row)
		for user in handlers:
			per_user[user].append(row)
	for user, rows in per_user.items():
		add(digests, [user], title, cols, rows)
	add(digests, get_managers(), title, cols, everything)


def pending_actions(digests):
	"""Open follow-ups grouped by principal: Action Required (overdue) / Action Pending."""
	cols = [_("Principal"), _("Customer"), _("Next Action"), _("Due"), _("Status"), _("Salesperson"), _("Visit")]
	rows = sorted(open_follow_ups(), key=lambda r: (r.principal or "~", r.customer_name or "", str(r.due or "")))
	per_user = defaultdict(list)
	everything = []
	for r in rows:
		overdue = r.due and getdate(r.due) < getdate(today())
		row = [
			r.principal or _("No principal"),
			r.customer_name,
			r.action,
			formatdate(r.due) if r.due else "",
			_("Action Required") if overdue else _("Action Pending"),
			r.salesperson_name,
			link("daily-visit-report", r.dvr),
		]
		everything.append(row)
		if r.salesperson:
			per_user[r.salesperson].append(row)
	title = _("Pending actions by principal")
	for user, user_rows in per_user.items():
		add(digests, [user], title, cols, user_rows)
	add(digests, get_managers(), title, cols, everything)


def missing_customer_data(digests):
	fy = current_fiscal_year()
	agents = get_agents()
	has = {
		"plant": set(frappe.get_all("Plant", filters={"is_active": 1}, pluck="customer", distinct=True)),
		"turnover": set(frappe.get_all("Customer Turnover", filters={"financial_year": fy}, pluck="customer", distinct=True)),
		"segment": set(frappe.get_all("Customer Segment Application", pluck="customer", distinct=True)),
		"principal": set(frappe.get_all("Customer Principal", filters={"parenttype": "TP Customer"}, pluck="parent", distinct=True)),
	}
	cols = [_("Customer"), _("Status"), _("Missing"), _("Handled By")]
	per_user = defaultdict(list)
	everything = []
	for c in frappe.get_all(
		"TP Customer",
		filters={"customer_status": ("!=", "Inactive")},
		fields=["name", "customer_name", "customer_status", "primary_contact_name", "industry_domain", "territory_region"],
		order_by="customer_name",
	):
		missing = [
			label
			for label, ok in (
				(_("Primary contact"), c.primary_contact_name),
				(_("Plant"), c.name in has["plant"]),
				(_("Industry"), c.industry_domain),
				(_("Region"), c.territory_region),
				(_("Turnover {0}").format(fy), c.name in has["turnover"]),
				(_("Segment / line application"), c.name in has["segment"]),
				(_("Principal"), c.name in has["principal"]),
				(_("Salesperson"), agents.get(c.name)),
			)
			if not ok
		]
		if not missing:
			continue
		handlers = agents.get(c.name, [])
		row = [
			link("tp-customer", c.name, c.customer_name),
			c.customer_status,
			", ".join(missing),
			", ".join(get_fullname(u) for u in handlers) or _("Not assigned"),
		]
		everything.append(row)
		for user in handlers:
			per_user[user].append(row)
	title = _("Customer data still missing")
	for user, rows in per_user.items():
		add(digests, [user], title, cols, rows)
	add(digests, get_managers(), title, cols, everything)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def open_follow_ups():
	"""Open To Dos created from Visit Reports, with the visit's customer and principal."""
	rows = frappe.db.sql(
		"""
		select todo.allocated_to as salesperson, todo.date as due, dvr.name as dvr,
			dvr.customer_name, dvr.principal, coalesce(dvr.next_action, todo.description) as action
		from `tabToDo` todo
		join `tabDaily Visit Report` dvr on dvr.name = todo.reference_name
		where todo.reference_type = 'Daily Visit Report' and todo.status = 'Open' and dvr.docstatus = 1
		""",
		as_dict=True,
	)
	for r in rows:
		r.salesperson_name = get_fullname(r.salesperson) if r.salesperson else ""
	return rows


def get_last_visits():
	return dict(
		frappe.db.sql(
			"select customer, max(visit_date) from `tabDaily Visit Report` where docstatus < 2 group by customer"
		)
	)


def get_agents():
	agents = defaultdict(list)
	for row in frappe.get_all(
		"Customer Agent", filters={"parenttype": "TP Customer"}, fields=["parent", "agent"], order_by="idx"
	):
		if row.agent:
			agents[row.parent].append(row.agent)
	return agents


def get_managers():
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ("in", MANAGER_ROLES)}, pluck="parent", distinct=True
	)
	return [u for u in users if u != "Administrator"]


def current_fiscal_year():
	"""Indian fiscal year (April–March) as in the spec, e.g. 2026-2027."""
	d = getdate(today())
	start = d.year if d.month >= 4 else d.year - 1
	return f"{start}-{start + 1}"


# ---------------------------------------------------------------------------
# Building and sending the digests
# ---------------------------------------------------------------------------


def add(digests, users, title, cols, rows):
	if not rows:
		return
	for user in users:
		digests[user].append((title, cols, rows))


def link(route, name, label=None):
	return f'<a href="{frappe.utils.get_url()}/app/{route}/{name}">{escape_html(str(label or name))}</a>'


def render(user, sections):
	html = [f"<p>{_('Dear {0},').format(escape_html(get_fullname(user)))}</p>"]
	for title, cols, rows in sections:
		html.append(f"<h4 style='margin:18px 0 6px'>{escape_html(title)} ({len(rows)})</h4>")
		html.append("<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;font-size:13px'>")
		html.append("<tr style='background:#f3f3f3'>" + "".join(f"<th align='left'>{escape_html(c)}</th>" for c in cols) + "</tr>")
		for row in rows:
			cells = "".join(f"<td>{v if isinstance(v, str) and v.startswith('<a ') else escape_html(str(v or ''))}</td>" for v in row)
			html.append(f"<tr>{cells}</tr>")
		html.append("</table>")
	html.append(f"<p style='color:#888;margin-top:18px'>{_('Sent automatically by TechPark.')}</p>")
	return "".join(html)


def deliver(digests, subject, link_to, dry_run=False):
	if dry_run:
		return digests
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	send_email = get_setting("reminder_emails") and has_outgoing_email()
	for user, sections in digests.items():
		enabled, email = frappe.db.get_value("User", user, ["enabled", "email"]) or (0, None)
		if not enabled:
			continue
		count = sum(len(rows) for _title, _cols, rows in sections)
		html = render(user, sections)
		try:
			enqueue_create_notification(
				user,
				{
					"type": "Alert",
					"subject": f"{subject} ({count})",
					"email_content": html,
					"link": link_to,
					"from_user": "Administrator",
				},
			)
			if send_email and email:
				frappe.sendmail(recipients=[email], subject=f"{subject} ({count})", message=html)
		except Exception:
			frappe.log_error(title=f"TechPark reminder failed for {user}")
	return digests


def has_outgoing_email():
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
		or frappe.conf.get("mail_server")
	)
