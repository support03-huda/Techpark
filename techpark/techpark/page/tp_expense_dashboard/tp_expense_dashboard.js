// Copyright (c) 2026, Techpark International
// Expense Dashboard page: amounts per status as tiles, claimed vs approved per month, top expense types,
// employees and customers, and the expenses waiting for approval with the days waited.
// Filters (period, dates, employee) sit in one row above everything. Every list can be exported (CSV).

// Server method of the page.
const TP_EXPENSE_DASHBOARD_METHOD = "techpark.expense_dashboard.get_dashboard";
// First month of the financial year (April).
const TP_EXPENSE_YEAR_START = 4;
// Chart colours: claimed (series 1, blue) and approved (series 2, orange); checked for colour blindness and
// contrast, with darker steps for the light theme and lighter ones for the dark theme.
const TP_EXPENSE_CHART_COLORS = {
	light: { claimed: "#2a78d6", approved: "#eb6834" },
	dark: { claimed: "#3987e5", approved: "#d95926" },
};
// Colour per status, as in the expense list.
const TP_EXPENSE_STATUS_COLORS = { "Pending Manager": "orange", "Pending Admin": "blue" };

// Look of the page; the colours also work in dark mode.
const TP_EXPENSE_DASHBOARD_STYLE = `
	.tp-xdash { max-width: 1200px; margin: 0 auto; padding: 8px 0 24px; }
	.tp-xdash h5 { margin: 28px 0 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.tp-xdash .tp-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
	.tp-xdash .tp-tile { padding: 14px 16px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--card-bg); }
	.tp-xdash .tp-tile-label { font-size: 12px; color: var(--text-muted); }
	.tp-xdash .tp-tile-value { font-size: 22px; font-weight: 600; margin-top: 2px; }
	.tp-xdash .tp-tile-note { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
	.tp-xdash .tp-tile-link { cursor: pointer; }
	.tp-xdash .tp-tile-link:hover { border-color: var(--primary); }
	.tp-xdash .tp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px 24px; }
	.tp-xdash .tp-panel { border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 16px; min-width: 0; background: var(--card-bg); }
	.tp-xdash .tp-panel h5 { margin: 0 0 8px; font-size: 14px; }
	.tp-xdash .tp-bar-row { display: grid; grid-template-columns: minmax(90px, 38%) 1fr auto; align-items: center; gap: 8px; margin: 6px 0; font-size: 13px; }
	.tp-xdash .tp-bar-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.tp-xdash .tp-bar-track { height: 14px; }
	.tp-xdash .tp-bar-fill { height: 100%; min-width: 2px; border-radius: 0 4px 4px 0; }
	.tp-xdash .tp-bar-value { text-align: right; white-space: nowrap; color: var(--text-muted); }
	.tp-xdash .tp-legend { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
	.tp-xdash .tp-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
	.tp-xdash .tp-table-wrap { overflow-x: auto; }
	.tp-xdash table { font-size: 13px; margin-bottom: 0; }
	.tp-xdash td.tp-number, .tp-xdash th.tp-number { text-align: right; white-space: nowrap; }
	.tp-xdash .tp-empty { padding: 24px; text-align: center; color: var(--text-muted); }
	.tp-xdash .tp-late { color: var(--red-500); font-weight: 600; }
`;

// Frappe calls this once, when the page is first opened.
frappe.pages["tp-expense-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Expense Dashboard"), single_column: true });
	$(`<style>${TP_EXPENSE_DASHBOARD_STYLE}</style>`).appendTo(page.main);
	wrapper.tp_expense_dashboard = new TPExpenseDashboard(page);
};

// Frappe calls this every time the page is shown; figures may have changed meanwhile.
frappe.pages["tp-expense-dashboard"].on_page_show = function (wrapper) {
	wrapper.tp_expense_dashboard && wrapper.tp_expense_dashboard.load();
};

// The dashboard: filters, tiles, charts and lists.
class TPExpenseDashboard {
	constructor(page) {
		this.page = page;
		this.make_filters();
		this.$body = $(`<div class="tp-xdash"></div>`).appendTo(page.main);
		page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
	}

	make_filters() {
		this.period = this.page.add_field({
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: ["This Month", "Last Month", "This Quarter", "This Financial Year", "Last Financial Year", "Custom"]
				.map((value) => ({ value, label: __(value) })),
			default: "This Month",
			change: () => this.apply_period(),
		});
		this.from_date = this.page.add_field({ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", change: () => this.dates_changed() });
		this.to_date = this.page.add_field({ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", change: () => this.dates_changed() });
		this.employee = this.page.add_field({
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "User",
			change: () => this.load(),
		});
		this.apply_period();
	}

	apply_period() {
		const today = moment(frappe.datetime.get_today());
		const period = this.period.get_value();
		if (period === "Custom") return;
		let start, end;
		const year_start = moment(today).month(TP_EXPENSE_YEAR_START - 1).startOf("month");
		if (year_start.isAfter(today)) year_start.subtract(1, "year");
		if (period === "This Month") [start, end] = [moment(today).startOf("month"), today];
		else if (period === "Last Month") [start, end] = [moment(today).subtract(1, "month").startOf("month"), moment(today).subtract(1, "month").endOf("month")];
		else if (period === "This Quarter") [start, end] = [moment(today).startOf("quarter"), today];
		else if (period === "This Financial Year") [start, end] = [year_start, today];
		else [start, end] = [moment(year_start).subtract(1, "year"), moment(year_start).subtract(1, "day")];
		this.setting_dates = true;
		this.from_date.set_value(start.format("YYYY-MM-DD"));
		this.to_date.set_value(end.format("YYYY-MM-DD")).then(() => {
			this.setting_dates = false;
			this.load();
		});
	}

	dates_changed() {
		if (this.setting_dates) return;
		if (this.period.get_value() !== "Custom") this.period.set_value("Custom");
		this.load();
	}

	load() {
		if (!this.from_date.get_value() || !this.to_date.get_value()) return;
		this.$body.html(`<div class="tp-empty">${__("Loading...")}</div>`);
		frappe
			.call(TP_EXPENSE_DASHBOARD_METHOD, {
				from_date: this.from_date.get_value(),
				to_date: this.to_date.get_value(),
				employee: this.employee.get_value() || null,
			})
			.then((r) => this.render(r.message));
	}

	render(data) {
		this.data = data;
		this.$body.empty();
		this.render_tiles(data.tiles);
		this.render_trend(data.trend);
		const $grid = $(`<div class="tp-grid" style="margin-top: 16px;"></div>`).appendTo(this.$body);
		this.render_bars($grid, __("By Expense Type"), data.by_type, __("bills"), "bills", "type");
		this.render_bars($grid, __("By Employee"), data.by_employee, __("claims"), "claims", "employee");
		this.render_bars($grid, __("By Customer"), data.by_customer, __("bills"), "bills", "customer");
		this.render_pending(data.pending);
	}

	render_tiles(t) {
		const tile = (label, value, note, route) =>
			`<div class="tp-tile ${route ? "tp-tile-link" : ""}" ${route ? `data-status="${route}"` : ""}>
				<div class="tp-tile-label">${label}</div>
				<div class="tp-tile-value">${value}</div>
				<div class="tp-tile-note">${note}</div>
			</div>`;
		const average = t.claims ? flt(t.claimed) / t.claims : 0;
		const $tiles = $(`<div class="tp-tiles">
			${tile(__("Total Claimed"), format_currency(t.claimed), __("{0} claim(s), average {1}", [t.claims, format_currency(average)]))}
			${tile(__("Approved"), format_currency(t.approved), __("{0} claim(s), {1} cut by admin", [cint(t.approved_count), format_currency(t.cut)]), "Approved")}
			${tile(__("Waiting for Manager"), format_currency(t.manager_amount), __("{0} claim(s)", [cint(t.manager_count)]), "Pending Manager")}
			${tile(__("Waiting for Admin"), format_currency(t.admin_amount), __("{0} claim(s)", [cint(t.admin_count)]), "Pending Admin")}
			${tile(__("Drafts"), cint(t.draft_count), __("{0} returned after rejection", [cint(t.returned_count)]), "Draft")}
		</div>`).appendTo(this.$body);
		$tiles.find(".tp-tile-link").on("click", (e) => {
			frappe.set_route("List", "TP Expense", {
				status: $(e.currentTarget).data("status"),
				entry_date: ["between", [this.from_date.get_value(), this.to_date.get_value()]],
			});
		});
	}

	render_trend(trend) {
		const colors = TP_EXPENSE_CHART_COLORS[document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"];
		const $panel = $(`<div class="tp-panel" style="margin-top: 16px;">
			<h5>${__("Claimed vs Approved, last 12 months")}</h5>
			<div class="tp-legend">
				<span><span class="tp-swatch" style="background:${colors.claimed}"></span>${__("Claimed")}</span>
				<span><span class="tp-swatch" style="background:${colors.approved}"></span>${__("Approved")}</span>
			</div>
			<div class="tp-trend"></div>
		</div>`).appendTo(this.$body);
		new frappe.Chart($panel.find(".tp-trend").get(0), {
			type: "bar",
			height: 260,
			data: {
				labels: trend.labels,
				datasets: [
					{ name: __("Claimed"), values: trend.claimed },
					{ name: __("Approved"), values: trend.approved },
				],
			},
			colors: [colors.claimed, colors.approved],
			barOptions: { spaceRatio: 0.4 },
			axisOptions: { xAxisMode: "tick", shortenYAxisNumbers: 1 },
			tooltipOptions: { formatTooltipY: (value) => format_currency(value) },
			showLegend: 0,
		});
	}

	render_bars($grid, title, rows, count_label, count_field, key) {
		const color = TP_EXPENSE_CHART_COLORS[document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"].claimed;
		const max = Math.max(...rows.map((row) => flt(row.amount)), 0);
		const $panel = $(`<div class="tp-panel">
			<h5>${title}<button class="btn btn-xs btn-default tp-export">${__("Export")}</button></h5>
		</div>`).appendTo($grid);
		$panel.find(".tp-export").on("click", () =>
			this.export(title, [[__("Name"), __("Amount"), frappe.utils.to_title_case(count_label)], ...rows.map((row) => [row.label, flt(row.amount), row[count_field]])])
		);
		if (!rows.length) {
			$panel.append(`<div class="tp-empty">${__("No expenses in this period.")}</div>`);
			return;
		}
		rows.forEach((row) => {
			const width = max ? (flt(row.amount) / max) * 100 : 0;
			$panel.append(`<div class="tp-bar-row" title="${frappe.utils.escape_html(row.label)}: ${format_currency(row.amount)}, ${row[count_field]} ${count_label}">
				<div class="tp-bar-name">${frappe.utils.escape_html(row.label)}</div>
				<div class="tp-bar-track"><div class="tp-bar-fill" style="width:${width}%; background:${color};"></div></div>
				<div class="tp-bar-value">${format_currency(row.amount)}</div>
			</div>`);
		});
	}

	render_pending(rows) {
		const $head = $(`<h5>${__("Waiting for Approval")} (${rows.length})<button class="btn btn-xs btn-default tp-export">${__("Export")}</button></h5>`).appendTo(this.$body);
		$head.find(".tp-export").on("click", () =>
			this.export(__("Waiting for Approval"), [
				[__("Expense"), __("Employee"), __("Status"), __("Waiting For"), __("Days Waiting"), __("Amount")],
				...rows.map((row) => [row.name, row.employee_name, row.status, row.waiting_for, row.days, flt(row.total_amount)]),
			])
		);
		if (!rows.length) {
			this.$body.append(`<div class="tp-panel tp-empty">${__("No expenses are waiting for approval.")}</div>`);
			return;
		}
		const esc = frappe.utils.escape_html;
		const body = rows
			.map(
				(row) => `<tr>
					<td><a href="/desk/tp-expense/${encodeURIComponent(row.name)}">${esc(row.name)}</a></td>
					<td>${esc(row.employee_name || "")}</td>
					<td><span class="indicator-pill ${TP_EXPENSE_STATUS_COLORS[row.status] || "gray"}">${__(row.status)}</span></td>
					<td>${esc(row.waiting_for || "")}</td>
					<td class="tp-number ${row.days > 3 ? "tp-late" : ""}">${__("{0} day(s)", [row.days])}</td>
					<td class="tp-number">${format_currency(row.total_amount)}</td>
				</tr>`
			)
			.join("");
		this.$body.append(`<div class="tp-panel tp-table-wrap"><table class="table table-bordered">
			<thead><tr><th>${__("Expense")}</th><th>${__("Employee")}</th><th>${__("Status")}</th><th>${__("Waiting For")}</th>
				<th class="tp-number">${__("Waiting")}</th><th class="tp-number">${__("Amount")}</th></tr></thead>
			<tbody>${body}</tbody></table></div>`);
	}

	export(title, rows) {
		// CSV download, opens in Excel; the period is in the file name.
		frappe.tools.downloadify(rows, null, `${title} ${this.from_date.get_value()} to ${this.to_date.get_value()}`);
	}
}
