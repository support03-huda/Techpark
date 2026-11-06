# Copyright (c) 2026, Techpark International
"""End-to-end checks for the Technical Lead / single-application DVR / Products Info changes.

	bench --site techpark.local execute techpark.dev_data.run_checks.execute

Everything it creates is rolled back at the end (nothing is left on the site).
Prints PASS / FAIL per check and a summary.
"""

import traceback

import frappe
from frappe.utils import today

RESULTS = []


def check(name, fn):
	try:
		detail = fn()
		RESULTS.append(("PASS", name, detail or ""))
	except Exception as e:  # noqa: BLE001 - report every failure and carry on
		RESULTS.append(("FAIL", name, f"{type(e).__name__}: {e}"))
		if frappe.conf.get("developer_mode"):
			traceback.print_exc()


def expect(cond, msg):
	if not cond:
		raise AssertionError(msg)


def expect_error(fn, contains=None):
	try:
		fn()
	except Exception as e:  # noqa: BLE001
		frappe.clear_messages()
		if contains and contains.lower() not in str(e).lower():
			raise AssertionError(f"wrong error: {e}") from e
		return f"blocked: {str(e)[:90]}"
	raise AssertionError("expected an error, none raised")


def execute():
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	ctx = frappe._dict()
	try:
		_meta_checks()
		_data_checks(ctx)
		_dvr_checks(ctx)
		_customer_checks(ctx)
		_report_checks(ctx)
	finally:
		frappe.db.rollback()
		frappe.flags.mute_emails = False
	_print()


# ---------------------------------------------------------------------------
def _fields(doctype):
	return {f.fieldname: f for f in frappe.get_meta(doctype).fields}


def _meta_checks():
	def technical_lead():
		f = _fields("TP Technical Lead")
		for n in ("customer", "principal", "application", "grinding_process", "supplier_product_category",
		          "annual_demand_amount", "share_noritake", "machine_maker", "size_od", "progress", "issue", "action_plan"):
			expect(n in f, f"TP Technical Lead.{n} missing")
		expect("process" not in f, "a field named 'process' would break Meta")
		expect(not frappe.get_meta("TP Technical Lead").quick_entry, "quick entry must be off (full form opens)")
		return "fields ok, full form on create"

	def dvr():
		f = _fields("Daily Visit Report")
		for n in ("dvr_stage", "principal", "technical_lead", "application", "development_status", "sales_status", "opportunity"):
			expect(n in f and not f[n].hidden, f"DVR.{n} missing or hidden")
		for n in ("contact", "contact_designation", "contact_phone", "visit_purpose", "department",
		          "application_potentials", "competitor_line_activity", "segment_application", "principals"):
			expect(f[n].hidden, f"DVR.{n} should be hidden")
		expect(not f["visit_purpose"].reqd and not f["department"].reqd, "visit purpose / department still mandatory")
		expect(not f["principals"].reqd, "principals table still mandatory")
		expect(f["development_status"].allow_on_submit and f["sales_status"].allow_on_submit, "statuses must be Allow on Submit")
		return "line fields shown, removed fields hidden"

	def customer():
		f = _fields("TP Customer")
		expect(f["tab_production"].label == "Products Info", f"tab label is {f['tab_production'].label}")
		expect(f["tab_technical"].label == "Technical Lead", "Technical tab label")
		expect("tab_products" not in f and "products_html" not in f, "old Products tab still there")
		for n in ("production", "abrasive_consumption_cr", "manufacturing_profile", "heat_treatment", "machines",
		          "wheel_specs", "technical_leads"):
			expect(n in f, f"TP Customer.{n} missing")
		for n in ("segment_applications", "consumptions", "manufacturing_details"):
			expect(n not in f, f"TP Customer.{n} should be removed")
		return "Products Info / Technical Lead tabs ok"

	check("meta: TP Technical Lead", technical_lead)
	check("meta: DVR form", dvr)
	check("meta: TP Customer tabs", customer)


# ---------------------------------------------------------------------------
def _data_checks(ctx):
	def demand_survey():
		leads = frappe.db.count("TP Technical Lead")
		expect(leads >= 133, f"only {leads} technical leads (expected 133 from the sheet)")
		ctx.customer = frappe.db.get_value("TP Customer", {"customer_name": "SKF India Ltd - PUNE"})
		expect(ctx.customer, "customer SKF India Ltd - PUNE not found")
		rows = frappe.get_all(
			"TP Technical Lead", filters={"customer": ctx.customer},
			fields=["name", "principal", "application", "supplier_product_category"], order_by="creation",
		)
		expect(len(rows) >= 2, "SKF Pune needs at least 2 leads")
		ctx.lead1, ctx.lead2 = rows[0], rows[1]
		tab = frappe.db.count("TP Customer Technical Lead", {"parent": ctx.customer, "parentfield": "technical_leads"})
		expect(tab == len(rows), f"customer tab shows {tab} rows, records {len(rows)}")
		return f"{leads} leads; SKF Pune: {len(rows)} on its tab"

	check("data: Demand Survey loaded", demand_survey)


# ---------------------------------------------------------------------------
def _dvr(ctx, stage, lead, **extra):
	return frappe.get_doc(
		{
			"doctype": "Daily Visit Report",
			"visit_date": today(),
			"customer": ctx.customer,
			"dvr_type": "Visit",
			"dvr_stage": stage,
			"visited_by": "Administrator",
			"principal": lead.principal,
			"technical_lead": lead.name,
			"discussion_notes": "run_checks",
			**extra,
		}
	)


def _dvr_checks(ctx):
	if not ctx.get("lead1"):
		RESULTS.append(("SKIP", "DVR checks", "no technical leads to test with"))
		return

	def single_line():
		dvr = _dvr(ctx, "Development", ctx.lead1, development_status="Introduction").insert()
		ctx.dvr1 = dvr
		expect(len(dvr.principals) == 1, f"{len(dvr.principals)} hidden rows, expected 1")
		row = dvr.principals[0]
		expect(row.application == ctx.lead1.application, f"row application {row.application!r}")
		expect(dvr.application == ctx.lead1.application, "visit application not filled from the lead")
		expect(row.technical_lead == ctx.lead1.name, "row technical lead")
		expect(row.stage == "Development" and dvr.dvr_stage == "Development", "stage")
		expect(dvr.stage_completed == 5, f"progress {dvr.stage_completed}")
		return f"{dvr.name}: 1 row '{row.application}', Development 5%"

	def submit_opportunity():
		dvr = ctx.dvr1
		dvr.submit()
		dvr.reload()
		opp = dvr.principals[0].opportunity
		expect(opp, "no opportunity on the row")
		expect(dvr.opportunity == opp, "opportunity not shown on the visit")
		o = frappe.get_doc("TP Opportunity", opp)
		expect(o.application == ctx.lead1.application and o.customer == ctx.customer, "opportunity line")
		ctx.opp1 = opp
		return f"{opp} ({o.status})"

	def another_application():
		dvr = _dvr(ctx, "Development", ctx.lead2, development_status="Enquiry Received").insert()
		dvr.submit()
		dvr.reload()
		expect(dvr.opportunity and dvr.opportunity != ctx.opp1, "second application must be its own opportunity")
		return f"{dvr.name} -> {dvr.opportunity}"

	def status_after_submit():
		dvr = frappe.get_doc("Daily Visit Report", ctx.dvr1.name)
		dvr.development_status = "Offer Submitted"
		dvr.save()
		dvr.reload()
		expect(dvr.principals[0].development_status == "Offer Submitted", "row not updated after submit")
		expect(frappe.db.get_value("TP Opportunity", ctx.opp1, "status") == "Offer Submitted", "opportunity not updated")
		return "row + opportunity moved to Offer Submitted"

	def sales_needs_status():
		return expect_error(lambda: _dvr(ctx, "Sales", ctx.lead1).insert(), "Sales Status")

	def sales_visit():
		dvr = _dvr(ctx, "Sales", ctx.lead1, sales_status="Enquiry Follow-up").insert()
		row = dvr.principals[0]
		expect(row.development_status == "Successful Trial" and row.stage == "Sales", "sales row stage")
		expect(dvr.dvr_stage == "Sales" and dvr.stage_completed == 75, f"progress {dvr.stage_completed}")
		dvr.submit()
		return f"{dvr.name}: Sales 75%"

	def development_after_sales():
		return expect_error(
			lambda: _dvr(ctx, "Development", ctx.lead1, development_status="Introduction").insert(), "Sales stage"
		)

	def cross_customer_lead():
		other = frappe.db.get_value("TP Technical Lead", {"customer": ("!=", ctx.customer)}, ["name", "principal", "application"], as_dict=True)
		if not other:
			return "skipped (no other customer's lead)"
		return expect_error(
			lambda: _dvr(ctx, "Development", other, development_status="Introduction").insert(), "another customer"
		)

	check("DVR: one line -> one hidden row", single_line)
	if ctx.get("dvr1"):
		check("DVR: submit creates the opportunity", submit_opportunity)
		check("DVR: another application = its own opportunity", another_application)
		check("DVR: status moves after submit", status_after_submit)
	check("DVR: Sales visit requires Sales Status", sales_needs_status)
	check("DVR: Sales visit", sales_visit)
	check("DVR: Development visit blocked once the line is in Sales", development_after_sales)
	check("DVR: lead of another customer is blocked", cross_customer_lead)


# ---------------------------------------------------------------------------
def _customer_checks(ctx):
	if not ctx.get("customer"):
		return

	def products_info():
		c = frappe.get_doc("TP Customer", ctx.customer)
		unit = frappe.db.get_value("Unit", {}) or frappe.get_doc({"doctype": "Unit", "unit_name": "Pcs (test)", "active": 1}).insert().name
		app = frappe.db.get_value("Customer Application", {}) or frappe.get_doc(
			{"doctype": "Customer Application", "application_name": "Roll Grinding (test)", "is_active": 1}
		).insert().name
		c.abrasive_consumption_cr = 24
		c.manufacturing_profile = "Ball and TRB bearings"
		c.heat_treatment = "In-house"
		c.append("machines", {"machine_type": "Thread Grinding", "maker": "WMW, Reishauer", "quantity": 3})
		c.append("wheel_specs", {
			"application": app, "wheel_specification": "89A400K3V111", "wheel_size": "350x40x160",
			"wheel_speed": "50 M/S", "pitch_range": "0.5 - 1 MM", "annual_consumption": 10, "consumption_unit": unit,
		})
		c.append("technical_leads", {"principal": ctx.lead1.principal, "application": "Run Checks Line", "progress": "Quoted"})
		c.save()
		c.reload()
		wheel = c.wheel_specs[-1]
		expect(wheel.record and frappe.db.exists("Wheel Specification", wheel.record), "wheel row not saved as a Wheel Specification")
		lead = next((r for r in c.technical_leads if r.application == "Run Checks Line"), None)
		expect(lead and lead.record and frappe.db.exists("TP Technical Lead", lead.record), "tab row not saved as a TP Technical Lead")
		expect(c.machines[-1].maker == "WMW, Reishauer", "machine row")
		expect(c.abrasive_consumption_cr == 24, "abrasive consumption")
		ctx.wheel = wheel.record
		return f"wheel {wheel.record}, lead {lead.record}"

	def lead_record_to_tab():
		lead = frappe.get_doc({"doctype": "TP Technical Lead", "customer": ctx.customer, "principal": ctx.lead1.principal,
		                       "application": "Run Checks From Record"}).insert()
		on_tab = frappe.db.exists("TP Customer Technical Lead", {"parent": ctx.customer, "record": lead.name})
		expect(on_tab, "a lead made on its own form did not appear on the customer's tab")
		return lead.name

	def customer_card():
		html = frappe.get_print("TP Customer", ctx.customer, "Customer Card")
		for text in ("CUSTOMER CARD", "Technical Leads", "Current Wheel Usage", "Machine Details", "Company Profile", "Abrasive / Year"):
			expect(text in html, f"'{text}' missing in the print")
		expect("89A400K3V111" in html, "wheel spec not printed")
		return f"{len(html)} chars"

	check("Customer: Products Info saves (wheel usage, machines, abrasive, profile)", products_info)
	check("Customer: Technical Lead record shows on the tab", lead_record_to_tab)
	check("Customer: Customer Card print", customer_card)


# ---------------------------------------------------------------------------
def _report_checks(ctx):
	from techpark.tp_dashboard import get_dashboard, get_development_board

	def dashboard():
		data = get_dashboard()
		stages = data["visits"]["stages"]
		for s in ("Development", "Sales"):
			expect("by_type" in stages[s], f"{s} tab has no 'Type of visit' data")
		return "visits / stages / pipeline ok"

	def board():
		data = get_development_board(customer=ctx.get("customer"))
		return f"{len(data.get('lines', data) if isinstance(data, dict) else data)} entries"

	def application_report():
		from frappe.desk.query_report import run

		run("Application Development Status", filters={})
		return "runs"

	def tour_expense():
		from frappe.desk.query_report import run

		run("TP Tour Expense", filters={"from_date": "2026-01-01", "to_date": today()})
		return "runs"

	check("Report: TechPark Dashboard", dashboard)
	check("Report: Development Board", board)
	check("Report: Application Development Status", application_report)
	check("Report: TP Tour Expense", tour_expense)


# ---------------------------------------------------------------------------
def _print():
	width = max(len(r[1]) for r in RESULTS) + 2
	print("\n" + "=" * 100)
	for status, name, detail in RESULTS:
		print(f"{status:5} {name.ljust(width)} {detail}")
	print("=" * 100)
	passed = sum(1 for r in RESULTS if r[0] == "PASS")
	failed = sum(1 for r in RESULTS if r[0] == "FAIL")
	print(f"{passed} passed, {failed} failed, {len(RESULTS) - passed - failed} skipped. (All test data rolled back.)\n")
