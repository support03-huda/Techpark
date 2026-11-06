// Copyright (c) 2026, Techpark International
// Development Board: the Application Development Status as a board, like the client's Development Status
// sheet. Every application line (TP Opportunity) under its customer, with its stage on the client's cycle,
// next action and last visit; a strip of every status with its count (click = filter). Data:
// techpark.tp_dashboard.get_development_board. "Open as Report" opens the same lines as a script report (Excel).

const TPB_STAGE_COLOR = { Development: "#f08c00", Sales: "#1d6fb8" };
const TPB_RESULT = { Won: ["green", "#2f9e44"], Lost: ["red", "#d64545"], "On Hold": ["gray", "#64748b"] };
const TPB_IMPORTANCE = { High: "red", Medium: "amber", Low: "gray" };

frappe.pages["techpark-development-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Development Board"), single_column: true });
	wrapper.tp_board = new TPDevelopmentBoard(page);
};

frappe.pages["techpark-development-board"].on_page_show = function (wrapper) {
	if (wrapper.tp_board && wrapper.tp_board.loaded) wrapper.tp_board.refresh();
};

class TPDevelopmentBoard {
	constructor(page) {
		this.page = page;
		this.filters = { show: "Open" };
		this.status = "";
		this.make_filters();
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("Open as Report"), () =>
			frappe.set_route("query-report", "Application Development Status", { open_only: this.filters.show === "Open" ? 1 : 0 })
		);
		this.page.add_inner_button(__("Dashboard"), () => frappe.set_route("techpark-dashboard"));
		this.$body = $(`<div class="tpd"><div class="tpd-loading">${__("Loading...")}</div></div>`).appendTo(this.page.main);
		this.refresh();
	}

	make_filters() {
		const is_manager = ["Sales Manager", "TechPark Approver", "System Manager"].some((r) => frappe.user.has_role(r));
		[
			{ fieldname: "show", label: __("Show"), fieldtype: "Select", options: ["Open", "All", "Won", "Lost"].join("\n"), default: "Open" },
			{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "TP Customer" },
			{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
			is_manager ? { fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "User" } : null,
			{ fieldname: "importance", label: __("Importance"), fieldtype: "Select", options: "\nHigh\nMedium\nLow" },
		]
			.filter(Boolean)
			.forEach((df) => {
				this.page.add_field({
					...df,
					change: () => {
						const value = this.page.fields_dict[df.fieldname].get_value() || "";
						if ((this.filters[df.fieldname] || "") === value) return;
						this.filters[df.fieldname] = value;
						this.refresh();
					},
				});
			});
	}

	refresh() {
		return frappe
			.call({ method: "techpark.tp_dashboard.get_development_board", args: this.filters })
			.then(({ message }) => {
				this.data = message;
				this.loaded = true;
				this.render();
			});
	}

	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	days_to(date) {
		return date ? frappe.datetime.get_day_diff(date, this.data.today) : null;
	}

	is_open(r) {
		return !["Won", "Lost"].includes(r.lead_status);
	}

	is_overdue(r) {
		const d = this.days_to(r.next_action_date);
		return this.is_open(r) && d !== null && d < 0;
	}

	// ------------------------------------------------------------ layout
	render() {
		const rows = this.data.rows;
		this.$body.html(`
			${this.hero_html(rows)}
			<div class="tpd-section">${__("Where the lines stand")}<span class="tpd-muted">${__("click a status to see only those lines")}</span></div>
			<div class="tpd-strip"></div>
			<div class="tpd-board"></div>
		`);
		this.render_strip(rows);
		this.render_board(rows.filter((r) => !this.status || r.status === this.status));
	}

	hero_html(rows) {
		const open = rows.filter((r) => this.is_open(r));
		const dev = open.filter((r) => r.stage === "Development").length;
		const sales = open.filter((r) => r.stage === "Sales").length;
		const won = rows.filter((r) => r.lead_status === "Won").length;
		const overdue = rows.filter((r) => this.is_overdue(r)).length;
		const high = open.filter((r) => r.importance === "High").length;
		const customers = new Set(rows.map((r) => r.customer)).size;
		const in_sales = open.length ? Math.round((sales / open.length) * 100) : 0;
		return `<div class="tpd-hero">
			<h2>${__("Application Development Status")}</h2>
			<div class="tpd-sub">${__("Every application line: enquiry → offer → trial → bulk trial PO → regularised")} · ${frappe.datetime.str_to_user(this.data.today)}</div>
			<div class="tpd-hero-stats">
				<div class="tpd-hero-stat"><div class="v">${open.length}</div><div class="l">${__("Open lines")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${dev}</div><div class="l">${__("In development")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${sales}</div><div class="l">${__("In sales")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${won}</div><div class="l">${__("Won")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${high}</div><div class="l">${__("High importance")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${overdue}</div><div class="l">${__("Next action overdue")}</div></div>
				<div class="tpd-hero-stat"><div class="v">${customers}</div><div class="l">${__("Customers")}</div></div>
			</div>
			<div class="tpd-progress">
				<div class="t"><span>${__("Open lines past the trial (in sales)")}</span><span>${in_sales}%</span></div>
				<div class="bar"><span style="width:${in_sales}%"></span></div>
			</div>
		</div>`;
	}

	render_strip(rows) {
		const $strip = this.$body.find(".tpd-strip");
		const statuses = this.data.statuses;
		let last_stage = null;
		const all = $(`<div class="tpd-stage ${this.status ? "" : "active"}" style="--accent:#8e2229">
			<div class="c">${rows.length}</div><div class="l">${__("All lines")}</div></div>`)
			.on("click", () => this.set_status(""))
			.appendTo($strip);
		statuses.forEach((s) => {
			if (s.stage !== last_stage) {
				$strip.append(`<div class="tpd-stage-gap">${this.esc(__(s.stage))}</div>`);
				last_stage = s.stage;
			}
			const n = rows.filter((r) => r.status === s.status).length;
			const color = TPB_STAGE_COLOR[s.stage];
			$(`<div class="tpd-stage ${this.status === s.status ? "active" : ""}" style="--accent:${color}" title="${this.esc(__(s.status))}">
				<div class="c ${n ? "" : "zero"}">${n}</div><div class="l">${this.esc(__(s.status))}</div></div>`)
				.on("click", () => this.set_status(this.status === s.status ? "" : s.status))
				.appendTo($strip);
		});
		return all;
	}

	set_status(status) {
		this.status = status;
		this.render();
	}

	render_board(rows) {
		const $board = this.$body.find(".tpd-board");
		if (!rows.length) {
			$board.html(`<div class="tpd-panel"><div class="tpd-empty">${__("No application lines here. Lines are made from the Principals rows of submitted visits.")}</div></div>`);
			return;
		}
		// Customers in the order of their most important line
		const groups = new Map();
		rows.forEach((r) => {
			if (!groups.has(r.customer)) groups.set(r.customer, []);
			groups.get(r.customer).push(r);
		});
		const order = this.data.statuses.map((s) => s.status);
		groups.forEach((lines, customer) => {
			const c = lines[0];
			const meta = [c.region, c.industry, c.customer_status].filter(Boolean).map((v) => this.esc(v)).join(" · ");
			const $card = $(`<div class="tpd-cust" style="margin-bottom:12px">
				<div class="tpd-cust-head">
					<span class="name">${this.esc(c.customer_name || customer)}</span>
					<span class="meta">${meta}</span>
					<span class="count tpd-pill gray">${lines.length} ${lines.length === 1 ? __("line") : __("lines")}</span>
				</div>
			</div>`).appendTo($board);
			$card.find(".name").on("click", () => frappe.set_route("Form", "TP Customer", customer));
			lines.forEach((r) => $card.append(this.line(r, order)));
		});
	}

	line(r, order) {
		const color = TPB_RESULT[r.lead_status] ? TPB_RESULT[r.lead_status][1] : TPB_STAGE_COLOR[r.stage] || "#64748b";
		const cur = order.indexOf(r.status);
		// Steps of the main path (failures / hold / cancel sit on their own place in the list)
		const steps = order
			.map((s, i) => `<i class="${i < cur ? "done" : i === cur ? "cur" : ""}" title="${this.esc(__(s))}"></i>`)
			.join("");
		const d = this.days_to(r.next_action_date);
		let due = "";
		if (this.is_open(r) && d !== null) {
			due = d < 0 ? `<span class="tpd-pill red">${__("{0}d overdue", [-d])}</span>`
				: d === 0 ? `<span class="tpd-pill orange">${__("Today")}</span>`
				: d <= 3 ? `<span class="tpd-pill amber">${__("In {0}d", [d])}</span>`
				: `<span class="tpd-pill blue">${frappe.datetime.str_to_user(r.next_action_date)}</span>`;
		}
		const result = TPB_RESULT[r.lead_status] ? `<span class="tpd-pill ${TPB_RESULT[r.lead_status][0]}">${this.esc(__(r.lead_status))}</span>` : "";
		const sub = [r.principal, r.category_name, r.spec, r.size].filter(Boolean).map((v) => this.esc(v)).join(" · ");
		const $line = $(`<div class="tpd-line ${this.is_overdue(r) ? "overdue" : ""}" style="border-left-color:${color}; --accent:${color}">
			<div>
				<div class="app">${this.esc(r.application)}
					${r.importance ? `<span class="tpd-pill ${TPB_IMPORTANCE[r.importance]}" style="margin-left:6px">${this.esc(__(r.importance))}</span>` : ""}</div>
				<div class="sub">${sub}</div>
			</div>
			<div>
				<div class="status" style="color:${color}">${this.esc(__(r.status || __("No status")))} ${result}</div>
				<div class="tpd-steps">${steps}</div>
			</div>
			<div>
				<div class="next" title="${this.esc(r.next_action || "")}">${this.esc(r.next_action || __("No next action"))}</div>
				<div class="sub">${due}</div>
			</div>
			<div>
				<div class="sub">${r.last_visit ? __("Last visit") + "<br>" + frappe.datetime.str_to_user(r.last_visit) : ""}</div>
				<div class="sub">${__("{0} visit(s)", [r.visits || 0])}</div>
			</div>
			<div style="text-align:right">
				<div class="sub" style="margin-bottom:6px">${this.esc(r.sales_person_name || "")}</div>
				${this.is_open(r) ? `<button class="btn btn-xs btn-default" data-act="visit">${__("+ Visit")}</button>` : ""}
			</div>
		</div>`);
		$line.on("click", (e) => {
			if ($(e.target).closest("[data-act=visit]").length) {
				// Picked up by the visit form on load (daily_visit_report.js)
				techpark.new_visit_row = {
					application: r.application,
					principal: r.principal,
					supplier_product_category: r.supplier_product_category,
					spec: r.spec,
					size: r.size,
				};
				frappe.new_doc("Daily Visit Report", { customer: r.customer });
				return;
			}
			frappe.set_route("Form", "TP Opportunity", r.name);
		});
		return $line;
	}
}

frappe.provide("techpark");
