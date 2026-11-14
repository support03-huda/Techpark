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
		for n in ("dvr_stage", "principal", "application_master", "spec", "size", "production_line", "customer_product",
		          "development_status", "sales_status", "opportunity"):
			expect(n in f and not f[n].hidden, f"DVR.{n} missing or hidden")
		for n in ("application", "supplier_product_category", "technical_lead"):
			expect(f[n].hidden, f"DVR.{n} should be hidden (filled from the Application)")
		expect(f["spec"].label == "Principal Product Spec" and f["size"].label == "Principal Product Size", "spec / size labels")
		order = [x.fieldname for x in frappe.get_meta("Daily Visit Report").fields]
		section = order[order.index("section_principal") + 1 : order.index("column_break_principal")]
		left = [n for n in section if not f[n].hidden and f[n].depends_on != "eval:false"]
		expect(left == ["principal", "application_master", "customer_product", "production_line"], f"left side {left}")
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
		for n in ("production", "abrasive_consumption_cr", "technical_leads"):
			expect(n in f, f"TP Customer.{n} missing")
		for n in ("segment_applications", "consumptions", "manufacturing_details", "machines", "wheel_specs", "manufacturing_profile"):
			expect(n not in f, f"TP Customer.{n} should be removed")
		return "Products Info / Technical Lead tabs ok"

	check("meta: TP Technical Lead", technical_lead)
	check("meta: DVR form", dvr)
	check("meta: TP Customer tabs", customer)

	def hierarchy():
		expect("industry_domain" in _fields("Customer Product"), "Customer Product has no Industry Segment")
		f = _fields("Customer Application")
		expect(f["product"].reqd, "Application master: Product should be required")
		for n in ("supplier_product_category", "principal", "spec", "size", "production_line"):
			expect(n in f, f"Application master.{n} missing")
		return "Industry Segment -> Product -> Application"

	check("meta: Industry Segment -> Product -> Application", hierarchy)


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
		lead = frappe.db.get_value("TP Technical Lead", ctx.lead1.name, ["stage", "current_status"], as_dict=True)
		expect(lead.current_status == "Offer Submitted" and lead.stage == "Development", f"technical lead shows {lead}")
		tab = frappe.db.get_value("TP Customer Technical Lead", {"record": ctx.lead1.name}, "current_status")
		expect(tab == "Offer Submitted", f"customer tab row shows {tab!r}")
		return "row, opportunity, technical lead and customer tab moved to Offer Submitted"

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
	def common_application():
		# Bearing -> BB -> "Run Checks Common App", usable by any customer
		industry = frappe.db.get_value("TP Customer", ctx.customer, "industry_domain") or frappe.db.get_value("Industry Domain", {})
		product = frappe.get_doc({"doctype": "Customer Product", "product_name": "Run Checks BB", "industry_domain": industry}).insert()
		category = frappe.db.get_value("Supplier Product Category", {"principal": ctx.lead1.principal}, "name")
		app = frappe.get_doc({
			"doctype": "Customer Application", "application_name": "Run Checks Common App", "product": product.name,
			"supplier_product_category": category, "spec": "RC-SPEC", "size": "100x20x30", "production_line": "Line RC",
			"is_active": 1,
		}).insert()
		expect(app.industry_domain == industry, "Industry Segment not taken from the Product")
		ctx.common_app = app
		from techpark.application import application_query, line_details
		rows = application_query("Customer Application", "Run Checks", "name", 0, 20, {"customer": ctx.customer, "principal": ctx.lead1.principal})
		listed = {r[0]: r for r in rows}
		expect(app.name in listed, "common application not in the dropdown")
		expect(listed[app.name][1] == "Run Checks Common App" and listed[app.name][2] == "Run Checks BB", f"dropdown does not show the product: {listed[app.name]}")
		other = frappe.db.get_value("Principal", {"name": ("!=", ctx.lead1.principal)})
		if category and other:
			hidden = [r[0] for r in application_query("Customer Application", "Run Checks", "name", 0, 20, {"customer": ctx.customer, "principal": other})]
			expect(app.name not in hidden, "another principal's application shows in the dropdown")
		someone = frappe.db.get_value("TP Customer", {"name": ("!=", ctx.customer)})
		if someone:
			anyone = [r[0] for r in application_query("Customer Application", "Run Checks", "name", 0, 20, {"customer": someone, "principal": ctx.lead1.principal})]
			expect(app.name in anyone, "application not offered to another customer")
		filled = line_details(ctx.customer, ctx.lead1.principal, app.name)["application"]
		for k, v in (("spec", "RC-SPEC"), ("size", "100x20x30"), ("production_line", "Line RC"), ("product", product.name)):
			expect(str(filled.get(k)) == str(v), f"autofill {k}: {filled.get(k)!r}")
		dvr = frappe.get_doc({
			"doctype": "Daily Visit Report", "visit_date": today(), "customer": ctx.customer, "dvr_type": "Visit",
			"dvr_stage": "Development", "visited_by": "Administrator", "principal": ctx.lead1.principal,
			"application_master": app.name, "development_status": "Introduction", "discussion_notes": "run_checks",
			"spec": filled.spec, "size": filled.size, "production_line": filled.production_line, "customer_product": filled.product,
		}).insert()
		lead = frappe.get_doc("TP Technical Lead", dvr.technical_lead)
		expect(lead.customer == ctx.customer and lead.application_master == app.name, "customer's lead not made")
		expect(lead.production_line == "Line RC" and str(lead.product) == str(product.name), "lead did not take Production Line / Product")
		if category:
			expect(str(lead.supplier_product_category) == str(category), f"lead category {lead.supplier_product_category!r}, expected {category!r} (master principal {frappe.db.get_value('Customer Application', app.name, 'principal')!r})")
		expect(dvr.application == "Run Checks Common App", f"application name {dvr.application!r}")
		expect(dvr.product_name == "Run Checks BB", f"DVR list Product {dvr.product_name!r}")
		ctx.common_dvr = dvr
		return f"dropdown + autofill ok; lead {dvr.technical_lead} made"

	def submitted_keeps_name():
		# The master is renamed later: a submitted visit keeps its name and the customer still saves
		dvr = ctx.common_dvr
		dvr.submit()
		frappe.db.set_value("Customer Application", ctx.common_app.name, "application_name", "Run Checks Renamed")
		frappe.get_doc("TP Technical Lead", dvr.technical_lead).save()
		frappe.get_doc("TP Customer", ctx.customer).save()
		dvr.reload()
		expect(dvr.application == "Run Checks Common App", f"submitted visit renamed to {dvr.application!r}")
		return "customer saves, visit keeps its name"

	def development_done_without_customer():
		from techpark.techpark.doctype.daily_visit_report.daily_visit_report import development_done

		expect(development_done(principal=ctx.lead1.principal) is False, "should be False")
		return "no error"

	def own_data_only():
		from techpark.permission import dvr_query_conditions, is_manager

		email = "run.checks.salesmanager@example.com"
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "RC", "send_welcome_email": 0,
		                       "roles": [{"role": "Sales Manager"}, {"role": "Sales User"}]}).insert(ignore_permissions=True)
		expect(not is_manager(user.name), "a Sales Manager should not see everyone's")
		expect(dvr_query_conditions(user.name), "no DVR filter for a Sales Manager")
		expect(is_manager("Administrator"), "admin should see all")
		frappe.set_user(email)
		try:
			seen = frappe.get_list("Daily Visit Report", pluck="name", limit_page_length=0)
		finally:
			frappe.set_user("Administrator")
		expect(ctx.common_dvr.name not in seen, "sees someone else's DVR")
		return f"sees {len(seen)} DVRs (own only)"

	check("DVR: lead of another customer is blocked", cross_customer_lead)
	check("DVR: Application -> everything autofills, lead made", common_application)
	if ctx.get("common_dvr"):
		check("DVR: submitted visit keeps its name when the master is renamed", submitted_keeps_name)
		check("DVR: each user sees only their own", own_data_only)
	check("DVR: principal picked before customer -> no error", development_done_without_customer)


# ---------------------------------------------------------------------------
def _customer_checks(ctx):
	if not ctx.get("customer"):
		return

	def products_info():
		c = frappe.get_doc("TP Customer", ctx.customer)
		c.abrasive_consumption_cr = 24
		c.append("technical_leads", {"principal": ctx.lead1.principal, "application": "Run Checks Line", "progress": "Quoted"})
		c.save()
		c.reload()
		lead = next((r for r in c.technical_leads if r.application == "Run Checks Line"), None)
		expect(lead and lead.record and frappe.db.exists("TP Technical Lead", lead.record), "tab row not saved as a TP Technical Lead")
		expect(c.abrasive_consumption_cr == 24, "abrasive consumption")
		return f"lead {lead.record}"

	def lead_record_to_tab():
		lead = frappe.get_doc({"doctype": "TP Technical Lead", "customer": ctx.customer, "principal": ctx.lead1.principal,
		                       "application": "Run Checks From Record"}).insert()
		on_tab = frappe.db.exists("TP Customer Technical Lead", {"parent": ctx.customer, "record": lead.name})
		expect(on_tab, "a lead made on its own form did not appear on the customer's tab")
		return lead.name

	def customer_card():
		html = frappe.get_print("TP Customer", ctx.customer, "Customer Card")
		for text in ("CUSTOMER CARD", "Technical Leads", "Abrasive / Year"):
			expect(text in html, f"'{text}' missing in the print")
		return f"{len(html)} chars"

	check("Customer: Products Info + Technical Lead tab save", products_info)
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

	def application_wise():
		from frappe.desk.query_report import run

		result = run("Application Wise Status", filters={})
		rows = result["result"]
		levels = {i: [r for r in rows if r.get("indent") == i] for i in range(4)}
		expect(levels[0] and levels[1] and levels[2], "missing Industry / Product / Application levels")
		expect(all(r.get("is_group") for i in (0, 1, 2) for r in levels[i]), "group rows")
		return f"{len(levels[0])} segments, {len(levels[1])} products, {len(levels[2])} applications, {len(levels[3])} customer lines"

	check("Report: Application Wise Status", application_wise)


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
