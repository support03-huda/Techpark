// Copyright (c) 2026, Techpark International
// TechPark Dashboard (same look as the UG dashboard): greeting with the headline numbers, clickable KPI cards
// for follow-ups and the development funnel, charts of visits / pipeline / principals, what needs action,
// a sales-person table, customers and expenses. Salespeople see their own work, managers the team.
// Data: techpark.tp_dashboard.get_dashboard.

const TPD_COLORS = {
	maroon: "#8e2229", green: "#2f9e44", blue: "#1d6fb8", amber: "#e8a317", red: "#d64545",
	violet: "#6d5bd0", teal: "#0f9d8a", orange: "#f08c00", slate: "#64748b",
};
const TPD_STAGE_COLOR = { Development: "#f08c00", Sales: "#1d6fb8" };
const TPD_PALETTE = [TPD_COLORS.blue, TPD_COLORS.teal, TPD_COLORS.amber, TPD_COLORS.violet, TPD_COLORS.green, TPD_COLORS.orange, TPD_COLORS.slate, TPD_COLORS.maroon];

frappe.pages["techpark-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("TechPark Dashboard"), single_column: true });
	wrapper.tp_dashboard = new TPDashboard(page);
};

frappe.pages["techpark-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.tp_dashboard && wrapper.tp_dashboard.loaded) wrapper.tp_dashboard.refresh();
};

class TPDashboard {
	constructor(page) {
		this.page = page;
		this.page.set_primary_action(__("New Visit"), () => frappe.new_doc("Daily Visit Report"), "add");
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("Development Board"), () => frappe.set_route("techpark-development-board"));
		this.page.add_inner_button(__("New Customer"), () => frappe.new_doc("TP Customer"));
		this.page.add_inner_button(__("New Expense"), () => frappe.new_doc("TP Expense"));
		this.visit_stage = "Development";
		try {
			this.tab = localStorage.getItem("techpark_dashboard_tab");
		} catch (e) {
			this.tab = null;
		}
		this.$body = $(`<div class="tpd"><div class="tpd-loading">${__("Loading dashboard...")}</div></div>`).appendTo(this.page.main);
		this.refresh();
	}

	refresh() {
		return frappe.call({ method: "techpark.tp_dashboard.get_dashboard" }).then(({ message }) => {
			this.data = message;
			this.loaded = true;
			this.render();
		});
	}

	// ------------------------------------------------------------ helpers
	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	inr(value) {
		const v = Number(value) || 0;
		if (Math.abs(v) >= 1e7) return `₹ ${(v / 1e7).toFixed(2)} Cr`;
		if (Math.abs(v) >= 1e5) return `₹ ${(v / 1e5).toFixed(2)} L`;
		return `₹ ${format_number(v, null, 0)}`;
	}

	pct(part, whole) {
		return whole ? Math.min(100, Math.round((part / whole) * 100)) : 0;
	}

	days_to(date) {
		return date ? frappe.datetime.get_day_diff(date, this.data.today) : null;
	}

	due_pill(date) {
		const d = this.days_to(date);
		if (d === null) return `<span class="tpd-pill gray">${__("No date")}</span>`;
		if (d < 0) return `<span class="tpd-pill red">${__("{0}d overdue", [-d])}</span>`;
		if (d === 0) return `<span class="tpd-pill orange">${__("Today")}</span>`;
		if (d === 1) return `<span class="tpd-pill amber">${__("Tomorrow")}</span>`;
		return `<span class="tpd-pill blue">${frappe.datetime.str_to_user(date)}</span>`;
	}

	report(options) {
		frappe.set_route("query-report", "Application Development Status", Object.assign({ open_only: 0 }, options));
	}

	// ------------------------------------------------------------ layout
	render() {
		const d = this.data;
		const tabs = this.tabs(d);
		if (!tabs.some((t) => t.key === this.tab)) this.tab = tabs[0].key;
		this.$body.html(`
			${this.hero_html(d)}
			<div class="tpd-tabs">${tabs
				.map((t) => `<div class="tpd-tab ${t.key === this.tab ? "active" : ""}" data-tab="${t.key}">${this.esc(t.label)}${
					t.count ? `<span class="tpd-tab-count ${t.alert ? "alert" : ""}">${t.count}</span>` : ""}</div>`)
				.join("")}</div>
			<div class="tpd-pane"></div>
		`);
		this.$body.find(".tpd-tab").on("click", (e) => this.show_tab($(e.currentTarget).data("tab")));
		this.show_tab(this.tab);
	}

	// One tab at a time: only its blocks are in the page, so its charts are drawn at full width.
	tabs(d) {
		const f = d.follow_ups;
		return [
			{ key: "today", label: __("Today"), count: f.overdue + f.today, alert: f.overdue > 0 },
			{ key: "development", label: __("Development"), count: d.opportunities.open },
			{ key: "visits", label: __("Visits"), count: d.visits.this_month },
			{ key: "team", label: __("Sales Team") },
			{ key: "customers", label: __("Customers"), count: d.customers.total },
			{ key: "expenses", label: __("Expenses"), count: d.expenses.pending_count, alert: d.expenses.pending_count > 0 },
		];
	}

	show_tab(key) {
		this.tab = key;
		try {
			localStorage.setItem("techpark_dashboard_tab", key);
		} catch (e) {
			// private window: the tab just isn't remembered
		}
		this.$body.find(".tpd-tab").removeClass("active").filter(`[data-tab="${key}"]`).addClass("active");
		const d = this.data;
		const panes = {
			today: `
				<div class="tpd-grid tpd-action"></div>
				<div class="tpd-row">
					<div class="tpd-panel"><h4>${__("Open follow-ups")}<span class="tpd-muted">${__("earliest first")}</span></h4><div class="tpd-follow"></div></div>
					<div class="tpd-panel"><h4>${__("High-importance lines")}<span class="tpd-muted">${__("open")}</span></h4><div class="tpd-hot"></div></div>
				</div>`,
			development: `
				<div class="tpd-grid tpd-funnel"></div>
				<div class="tpd-row wide">
					<div class="tpd-panel"><h4>${__("Lines by status")}<span class="tpd-muted">${__("enquiry → trial → bulk trial PO → regularised")}</span></h4><div class="tpd-chart tpd-chart-pipeline"></div></div>
					<div class="tpd-panel"><h4>${__("Development vs Sales")}<span class="tpd-muted">${__("open lines")}</span></h4><div class="tpd-chart tpd-chart-split"></div></div>
				</div>
				<div class="tpd-panel"><h4>${__("High-importance lines")}<span class="tpd-muted"><a href="/desk/techpark-development-board">${__("Open Development Board")} →</a></span></h4><div class="tpd-hot"></div></div>`,
			visits: `
				<div class="tpd-subtabs">${["Development", "Sales"]
					.map((s) => `<div class="tpd-subtab ${s === this.visit_stage ? "active" : ""}" data-stage="${s}" style="--accent:${TPD_STAGE_COLOR[s]}">
						<span class="dot"></span>${this.esc(__(s + " Stage"))}<span class="n">${d.visits.stages[s].this_month}</span></div>`)
					.join("")}<span class="tpd-muted" style="margin-left:auto">${__("visits this month · a visit with both stages counts in both")}</span></div>
				<div class="tpd-visit-stage"></div>`,
			team: `
				<div class="tpd-panel"><h4>${__("Sales person-wise")}<span class="tpd-muted">${__("application lines; click a row to open the Development Board")}</span></h4>
					<div class="tpd-table-wrap tpd-people"></div></div>`,
			customers: `
				<div class="tpd-grid tpd-cust-kpis"></div>
				<div class="tpd-row">
					<div class="tpd-panel"><h4>${__("Customers by region")}</h4><div class="tpd-chart tpd-chart-region"></div></div>
					<div class="tpd-panel"><h4>${__("Customers by status")}</h4><div class="tpd-chart tpd-chart-status"></div></div>
				</div>`,
			expenses: `
				<div class="tpd-grid tpd-money"></div>
				<div class="tpd-panel"><h4>${__("Expenses per month")}<span class="tpd-muted">${__("claimed amount")}</span></h4><div class="tpd-chart tpd-chart-expense"></div></div>`,
		};
		this.$body.find(".tpd-pane").html(panes[key] || "");
		// Each block draws only when its place is on the page.
		this.render_action(d);
		this.render_follow_ups(d.follow_ups.list);
		this.render_hot(d.opportunities.hot);
		this.render_funnel(d);
		this.render_people(d.opportunities.by_person);
		this.render_customers(d);
		this.render_money(d.expenses);
		this.render_charts(d);
		if (key === "visits") {
			this.$body.find(".tpd-subtab").on("click", (e) => this.show_visit_stage($(e.currentTarget).data("stage")));
			this.show_visit_stage(this.visit_stage);
		}
	}

	// ------------------------------------------------------------ Visits tab: Development / Sales stage
	show_visit_stage(stage) {
		this.visit_stage = stage;
		this.$body.find(".tpd-subtab").removeClass("active").filter(`[data-stage="${stage}"]`).addClass("active");
		const s = this.data.visits.stages[stage];
		const color = TPD_STAGE_COLOR[stage];
		const $el = this.$body.find(".tpd-visit-stage");
		$el.html(`
			<div class="tpd-grid tpd-stage-kpis" style="margin-bottom:16px"></div>
			<div class="tpd-row wide" style="margin-bottom:16px">
				<div class="tpd-panel"><h4>${__("{0} visits per month", [__(stage)])}<span class="tpd-muted">${__("last 12 months")}</span></h4><div class="tpd-chart tpd-chart-stage-monthly"></div></div>
				<div class="tpd-panel"><h4>${__("Where the lines stood")}<span class="tpd-muted">${__("status on the visits")}</span></h4><div class="tpd-chart tpd-chart-stage-status"></div></div>
			</div>
			<div class="tpd-row" style="margin-bottom:16px">
				<div class="tpd-panel"><h4>${__("By principal")}<span class="tpd-muted">${__("lines discussed")}</span></h4><div class="tpd-chart tpd-chart-stage-principal"></div></div>
				<div class="tpd-panel"><h4>${__("By sales person")}<span class="tpd-muted">${__("visits")}</span></h4><div class="tpd-chart tpd-chart-stage-person"></div></div>
			</div>
			<div class="tpd-row wide">
				<div class="tpd-panel"><h4>${__("Latest {0} visits", [__(stage)])}</h4><div class="tpd-stage-recent"></div></div>
				<div class="tpd-panel"><h4>${__("Purpose of visit")}</h4><div class="tpd-chart tpd-chart-stage-purpose"></div></div>
			</div>`);

		const delta = s.last_month ? Math.round(((s.this_month - s.last_month) / s.last_month) * 100) : null;
		const list = () => frappe.set_route("List", "Daily Visit Report", { docstatus: 1, dvr_stage: ["like", `%${stage}%`] });
		this.kpis(".tpd-stage-kpis", [
			[__("Visits This Month"), s.this_month, delta === null ? __("{0} last month", [s.last_month]) : `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta)}% ${__("vs last month")}`, color, list],
			[__("Customers Visited"), s.customers_this_month, __("this month"), TPD_COLORS.teal, list],
			[__("Lines Worked On"), s.lines_this_month, __("application lines this month"), TPD_COLORS.violet, () => frappe.set_route("techpark-development-board")],
			[__("Last 12 Months"), s.total, __("{0} visits", [__(stage)]), TPD_COLORS.slate, list],
		]);

		const bar = (selector, rows, colors, extra) => {
			if (!rows.length) return this.empty(selector);
			this.chart(selector, Object.assign({
				type: "bar",
				data: { labels: rows.map((r) => __(r.label)), datasets: [{ name: __("Count"), values: rows.map((r) => r.value) }] },
				colors,
				barOptions: { spaceRatio: 0.4 },
			}, extra || {}));
		};
		if (s.monthly.some((m) => m.value)) {
			this.chart(".tpd-chart-stage-monthly", {
				type: "axis-mixed",
				data: { labels: s.monthly.map((m) => m.month), datasets: [{ name: __("Visits"), values: s.monthly.map((m) => m.value), chartType: "bar" }] },
				colors: [color],
				barOptions: { spaceRatio: 0.45 },
			});
		} else {
			this.empty(".tpd-chart-stage-monthly", __("No {0} visits in the last 12 months.", [__(stage)]));
		}
		bar(".tpd-chart-stage-status", s.by_status, [color]);
		bar(".tpd-chart-stage-principal", s.by_principal, [TPD_COLORS.violet]);
		bar(".tpd-chart-stage-person", s.by_person, [TPD_COLORS.teal]);
		if (s.by_purpose.length) {
			this.chart(".tpd-chart-stage-purpose", {
				type: "donut",
				data: { labels: s.by_purpose.map((r) => __(r.label)), datasets: [{ values: s.by_purpose.map((r) => r.value) }] },
				colors: TPD_PALETTE,
			});
		} else {
			this.empty(".tpd-chart-stage-purpose");
		}

		const pill = stage === "Sales" ? "blue" : "orange";
		this.list(".tpd-stage-recent", s.recent,
			(r) => `<div class="main"><div class="n">${this.esc(r.customer)}
					<span class="tpd-muted" style="font-weight:normal"> · ${frappe.datetime.str_to_user(r.date)} · ${this.esc(r.by || "")}</span></div>
				<div class="d">${r.lines.map((l) => `${this.esc([l.application, l.principal].filter(Boolean).join(" · "))}: <span class="tpd-pill ${pill}">${this.esc(__(l.status))}</span>`).join(" &nbsp; ")}</div></div>`,
			(r) => frappe.set_route("Form", "Daily Visit Report", r.name),
			__("No {0} visits yet.", [__(stage)]));
	}

	// Greeting only: the numbers are in the tabs (the user asked to drop the header's number cards).
	hero_html(d) {
		const name = frappe.boot.user.first_name || (d.user.name || "").split(" ")[0];
		const hour = new Date().getHours();
		const greet = hour < 12 ? __("Good morning") : hour < 17 ? __("Good afternoon") : __("Good evening");
		return `<div class="tpd-hero">
			<h2>${this.esc(greet)}${name ? ", " + this.esc(name) : ""}</h2>
			<div class="tpd-sub">${__("TechPark International")} · ${d.user.is_manager ? __("whole team") : __("your work")} · ${frappe.datetime.str_to_user(d.today)}</div>
		</div>`;
	}

	kpis(selector, cards) {
		const $grid = this.$body.find(selector);
		cards.forEach(([label, value, sub, color, action, display]) => {
			$(`<div class="tpd-kpi" style="--accent:${color}">
				<div class="l"><span class="dot"></span>${this.esc(label)}</div>
				<div class="v">${display != null ? display : format_number(value || 0, null, 0)}</div>
				<div class="s">${this.esc(sub)}</div></div>`)
				.on("click", action)
				.appendTo($grid);
		});
	}

	render_action(d) {
		const f = d.follow_ups;
		const todo = (date) => () => frappe.set_route("List", "ToDo", { status: "Open", reference_type: "Daily Visit Report", date });
		this.kpis(".tpd-action", [
			[__("Overdue Follow-ups"), f.overdue, __("date has passed: call or visit"), TPD_COLORS.red, todo(["<", frappe.datetime.get_today()])],
			[__("Due Today"), f.today, __("follow-ups for today"), TPD_COLORS.orange, todo(frappe.datetime.get_today())],
			[__("Due This Week"), f.week, __("next 7 days"), TPD_COLORS.amber, todo(["between", [frappe.datetime.get_today(), frappe.datetime.add_days(frappe.datetime.get_today(), 7)]])],
			[__("Prospects Waiting"), f.stale_prospects, __("prospect for {0}+ days", [f.stale_days]), TPD_COLORS.violet, () => frappe.set_route("List", "TP Customer", { customer_status: "Prospect" })],
			[__("Lines Overdue"), d.opportunities.overdue, __("next action date passed"), TPD_COLORS.maroon, () => frappe.set_route("techpark-development-board")],
		]);
	}

	list(selector, rows, render, open, empty) {
		const $el = this.$body.find(selector);
		if (!rows || !rows.length) {
			$el.html(`<div class="tpd-empty">${this.esc(empty)}</div>`);
			return;
		}
		$el.html(`<ul class="tpd-list">${rows.map((r, i) => `<li data-i="${i}">${render(r)}</li>`).join("")}</ul>`);
		$el.find("li").on("click", (e) => open(rows[$(e.currentTarget).data("i")]));
	}

	render_follow_ups(rows) {
		this.list(".tpd-follow", rows,
			(r) => `<div class="main"><div class="n">${this.esc(r.customer)}</div><div class="d">${this.esc(r.note || "")}${r.owner && this.data.user.is_manager ? " · " + this.esc(r.owner) : ""}</div></div>${this.due_pill(r.date)}`,
			(r) => frappe.set_route("Form", "Daily Visit Report", r.visit),
			__("No open follow-ups. All caught up!"));
	}

	render_hot(rows) {
		this.list(".tpd-hot", rows,
			(r) => `<div class="main"><div class="n">${this.esc(r.customer)} · ${this.esc(r.application)}</div>
				<div class="d">${this.esc([r.principal, r.status].filter(Boolean).join(" · "))}</div></div>${this.due_pill(r.date)}`,
			(r) => frappe.set_route("Form", "TP Opportunity", r.name),
			__("No High-importance lines. Set Importance on an opportunity."));
	}

	render_funnel(d) {
		const o = d.opportunities;
		const p = d.pipeline;
		const board = () => frappe.set_route("techpark-development-board");
		this.kpis(".tpd-funnel", [
			[__("In Development"), o.development, __("enquiry to trial"), TPD_COLORS.orange, () => this.report({ stage: "Development", open_only: 1 })],
			[__("Trials Running"), p.trials, __("trial PO / sample / trial"), TPD_COLORS.teal, () => this.report({ stage: "Development" })],
			[__("Successful Trials"), p.successful, __("waiting for bulk trial PO"), TPD_COLORS.violet, () => this.report({ status: "Successful Trial" })],
			[__("Bulk Trial PO"), p.won, __("first order after the trial"), TPD_COLORS.green, () => this.report({ status: "Bulk Trial PO" })],
			[__("Regularised"), p.regularization, __("regular orders"), TPD_COLORS.blue, () => this.report({ status: "Regularization" })],
			[__("High Importance"), o.high, __("open lines"), TPD_COLORS.red, board],
		]);
	}

	render_people(people) {
		const $el = this.$body.find(".tpd-people");
		if (!people.length) {
			$el.html(`<div class="tpd-empty">${__("No application lines yet.")}</div>`);
			return;
		}
		const max = Math.max(...people.map((p) => p.open), 1);
		const head = [__("Sales Person"), __("Open Lines"), __("Development"), __("Sales"), __("Won"), __("Lost"), __("Overdue"), __("Visits This Month")];
		const body = people.map((p, i) => `<tr data-i="${i}">
			<td><b>${this.esc(p.name)}</b></td>
			<td><div class="tpd-bar-cell"><span>${p.open}</span><div class="tpd-meter" style="--accent:${TPD_COLORS.maroon}"><span style="width:${this.pct(p.open, max)}%"></span></div></div></td>
			<td class="num">${p.development ? `<span class="tpd-pill orange">${p.development}</span>` : 0}</td>
			<td class="num">${p.sales ? `<span class="tpd-pill blue">${p.sales}</span>` : 0}</td>
			<td class="num">${p.won ? `<span class="tpd-pill green">${p.won}</span>` : 0}</td>
			<td class="num">${p.lost ? `<span class="tpd-pill gray">${p.lost}</span>` : 0}</td>
			<td class="num">${p.overdue ? `<span class="tpd-pill red">${p.overdue}</span>` : 0}</td>
			<td class="num">${p.visits}</td>
		</tr>`).join("");
		$el.html(`<table class="tpd-table"><thead><tr>${head.map((h, i) => `<th class="${i ? "num" : ""}">${this.esc(h)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`);
		$el.find("tr[data-i]").on("click", () => frappe.set_route("techpark-development-board"));
	}

	render_customers(d) {
		const c = d.customers;
		const list = (status) => () => frappe.set_route("List", "TP Customer", status ? { customer_status: status } : {});
		this.kpis(".tpd-cust-kpis", [
			[__("All Customers"), c.total, __("in the customer master"), TPD_COLORS.slate, list()],
			[__("Active Customers"), c.active, __("buying from us"), TPD_COLORS.green, list("Active Customer")],
			[__("Prospects"), c.prospects, __("not buying yet"), TPD_COLORS.amber, list("Prospect")],
		]);
	}

	render_money(e) {
		const go = (opts) => () => frappe.set_route("List", "TP Expense", opts || {});
		this.kpis(".tpd-money", [
			[__("Claimed This Month"), 0, __("all claims"), TPD_COLORS.blue, go(), this.inr(e.this_month)],
			[__("Approved This Month"), 0, __("passed amount"), TPD_COLORS.green, go({ status: "Approved" }), this.inr(e.approved_this_month)],
			[__("Waiting for Approval"), e.pending_count, this.inr(e.pending_amount) + " " + __("pending"), TPD_COLORS.orange, () => frappe.set_route("tp-expense-approvals")],
		]);
	}

	// ------------------------------------------------------------ charts
	chart(selector, options) {
		const el = this.$body.find(selector)[0];
		if (!el || !frappe.Chart) return;
		try {
			new frappe.Chart(el, Object.assign({ height: 250, animate: 1 }, options));
		} catch (e) {
			this.empty(selector);
		}
	}

	empty(selector, text) {
		this.$body.find(selector).html(`<div class="tpd-empty">${this.esc(text || __("No data yet."))}</div>`);
	}

	render_charts(d) {
		// Lines by status, Development (orange) then Sales (blue)
		const stages = d.pipeline.stages.filter((s) => s.value);
		if (stages.length) {
			this.chart(".tpd-chart-pipeline", {
				type: "bar",
				data: { labels: stages.map((s) => __(s.stage)), datasets: [{ name: __("Lines"), values: stages.map((s) => s.value) }] },
				colors: [TPD_COLORS.maroon],
				barOptions: { spaceRatio: 0.35 },
			});
		} else {
			this.empty(".tpd-chart-pipeline", __("No application lines yet."));
		}
		const o = d.opportunities;
		if (o.development || o.sales) {
			this.chart(".tpd-chart-split", {
				type: "donut",
				data: { labels: [__("Development"), __("Sales")], datasets: [{ values: [o.development, o.sales] }] },
				colors: [TPD_COLORS.orange, TPD_COLORS.blue],
			});
		} else {
			this.empty(".tpd-chart-split");
		}

		const group_chart = (selector, rows, type, colors) => {
			if (!rows.length) return this.empty(selector);
			this.chart(selector, {
				type,
				data: { labels: rows.map((r) => __(r.label)), datasets: [{ name: __("Count"), values: rows.map((r) => r.value) }] },
				colors,
				barOptions: { spaceRatio: 0.4 },
			});
		};
		group_chart(".tpd-chart-region", d.customers.by_region, "bar", [TPD_COLORS.teal]);
		group_chart(".tpd-chart-status", d.customers.by_status, "pie", [TPD_COLORS.green, TPD_COLORS.amber, TPD_COLORS.slate]);

		const e = d.expenses;
		if (e.monthly.some((m) => m.value)) {
			this.chart(".tpd-chart-expense", {
				type: "bar",
				data: { labels: e.monthly.map((m) => m.month), datasets: [{ name: __("Amount"), values: e.monthly.map((m) => m.value) }] },
				colors: [TPD_COLORS.amber],
				barOptions: { spaceRatio: 0.45 },
				tooltipOptions: { formatTooltipY: (value) => this.inr(value) },
			});
		} else {
			this.empty(".tpd-chart-expense", __("No expenses in the last 12 months."));
		}
	}
}
