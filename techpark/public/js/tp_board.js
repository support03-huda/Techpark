// Last edited: 2026-11-26
// Copyright (c) 2026, Techpark International
// Shared by the Development Board and the Sales Board pages (included by their page scripts).
// Every application line (TP Opportunity) of that stage under its customer, with its status on the
// client's cycle, milestones, next action and last visit; a strip of the stage's statuses (click = filter).
// Data: techpark.tp_dashboard.get_development_board(stage=...).

const TPB_STAGE_COLOR = { Development: "#f08c00", Sales: "#1d6fb8" };
const TPB_RESULT = { Won: ["green", "#2f9e44"], Lost: ["red", "#d64545"], "On Hold": ["gray", "#64748b"] };
const TPB_IMPORTANCE = { High: "red", Medium: "amber", Low: "gray" };

class TPBoard {
	// stage: "Development" or "Sales"
	constructor(page, stage) {
		this.page = page;
		this.stage = stage;
		this.filters = { show: "Open" };
		this.status = "";
		this.make_filters();
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("Open as Report"), () =>
			frappe.set_route("query-report", "Application Development Status", { open_only: this.filters.show === "Open" ? 1 : 0 })
		);
		this.page.add_inner_button(__("Dashboard"), () => frappe.set_route("techpark-dashboard"));
		const other = stage === "Sales" ? ["techpark-development-board", __("Development Board")] : ["techpark-sales-board", __("Sales Board")];
		this.page.add_inner_button(other[1], () => frappe.set_route(other[0]));
		this.$body = $(`<div class="tpd"><div class="tpd-loading">${__("Loading...")}</div></div>`).appendTo(this.page.main);
		this.refresh();
	}

	make_filters() {
		const is_manager = (frappe.boot.techpark_roles?.admin || []).some((r) => frappe.user.has_role(r)); // 2026-11-26: Admin Roles (TechPark Settings)
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
		// 2026-11-23: opened from the dashboard with a Sales Person picked -> same filter here
		const sp = frappe.route_options && frappe.route_options.sales_person;
		if (sp && this.page.fields_dict.sales_person) {
			frappe.route_options = null;
			this.filters.sales_person = sp;
			this.page.fields_dict.sales_person.set_value(sp);
		}
		return frappe
			.call({ method: "techpark.tp_dashboard.get_development_board", args: { ...this.filters, stage: this.stage } })
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
		const count = (statuses) => rows.filter((r) => statuses.includes(r.status)).length;
		const overdue = rows.filter((r) => this.is_overdue(r)).length;
		const high = open.filter((r) => r.importance === "High").length;
		const customers = new Set(rows.map((r) => r.customer)).size;
		const sales = this.stage === "Sales";
		const stats = sales
			? [
				[open.length, __("Open lines")],
				[count(["Successful Trial"]), __("Awaiting bulk PO")],
				[count(["Bulk Trial PO"]), __("Bulk trial PO")],
				[count(["Enquiry Follow-up", "Order Follow-up", "Delivery Follow-up", "Payment Follow-up"]), __("In follow-up")],
				[count(["Regularization"]), __("Regularised")],
				[overdue, __("Next action overdue")],
				[customers, __("Customers")],
			]
			: [
				[open.length, __("Open lines")],
				[count(["Introduction", "Enquiry Received", "Sent to Principal"]), __("Enquiry stage")],
				[count(["Offer Received", "Offer Submitted"]), __("Offer stage")],
				[count(["Trial PO Received", "Sample Received", "Trial in Progress", "Retest"]), __("In trial")],
				[count(["Trial Failed"]), __("Trial failed")],
				[overdue, __("Next action overdue")],
				[customers, __("Customers")],
			];
		const done = sales ? count(["Regularization"]) : count(["Trial PO Received", "Sample Received", "Trial in Progress", "Retest"]);
		const pct = open.length ? Math.round((done / open.length) * 100) : 0;
		return `<div class="tpd-hero ${sales ? "sales" : "dev"}">
			<h2>${sales ? __("Sales Board") : __("Development Board")}</h2>
			<div class="tpd-sub">${sales ? __("Lines past the trial: bulk trial PO → enquiry / order / delivery / payment follow-up → regularised") : __("Lines in development: enquiry → offer → trial PO → sample → trial")} · ${frappe.datetime.str_to_user(this.data.today)}</div>
			<div class="tpd-hero-stats">${stats.map(([v, l]) => `<div class="tpd-hero-stat"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("")}</div>
			<div class="tpd-progress">
				<div class="t"><span>${sales ? __("Open lines regularised") : __("Open lines in trial")}</span><span>${pct}%</span></div>
				<div class="bar"><span style="width:${pct}%"></span></div>
			</div>
			${high ? `<div class="tpd-sub" style="margin-top:6px">${__("{0} high-importance line(s)", [high])}</div>` : ""}
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
			$board.html(`<div class="tpd-panel"><div class="tpd-empty">${this.stage === "Sales" ? __("No lines in the Sales stage here.") : __("No lines in the Development stage here.")}</div></div>`);
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

	// Samples / Trials / Bulk Trials PO / Regularised, like the client's Development Status sheet
	milestones_html(r) {
		const color = {
			Successful: "green", Regularised: "green", Received: "blue", Supplied: "blue", "Received / Sent": "blue",
			"Can Use as Samples": "blue", "In Progress": "orange", "To Try": "orange", Failed: "red",
			"Cost Problem": "red", "Not Regularised": "red", "Not Tried": "gray",
		};
		const pills = [
			[__("Samples"), r.samples], [__("Trials"), r.trials], [__("Bulk PO"), r.bulk_trial_po], [__("Regularised"), r.regularised],
		]
			.filter(([, v]) => v)
			.map(([label, v]) => `<span class="tpd-pill ${color[v] || "gray"}" title="${this.esc(label)}">${this.esc(label)}: ${this.esc(__(v))}</span>`);
		return pills.length ? `<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:6px">${pills.join("")}</div>` : "";
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
				${r.present_status ? `<div class="sub tpd-present" title="${this.esc(r.present_status)}">${this.esc(r.present_status)}</div>` : ""}
				${this.milestones_html(r)}
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
				<div class="sub" style="margin-bottom:6px">${this.esc([r.sales_person_name, r.joint_with].filter(Boolean).join(" / "))}</div>
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
					stage: r.stage,
				};
				frappe.new_doc("Daily Visit Report", { customer: r.customer });
				return;
			}
			frappe.set_route("Form", "TP Opportunity", r.name);
		});
		return $line;
	}
}

