// TechPark Today — runs inside the Custom HTML Block's shadow DOM (`root_element` is
// its shadow root). Data: techpark.dashboard.get_today. Synced from the app on migrate.

const root = root_element.querySelector(".tp-today");
const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
const TAB_KEY = "techpark.today.tab";
let data = null;

function show_tab(tab) {
	root.querySelectorAll(".tp-tab").forEach((t) => {
		const active = t.dataset.tab === tab;
		t.classList.toggle("active", active);
		t.setAttribute("aria-selected", active ? "true" : "false");
	});
	root.querySelectorAll(".tp-pane").forEach((p) => (p.hidden = p.dataset.pane !== tab));
	try {
		localStorage.setItem(TAB_KEY, tab);
	} catch (e) {
		// storage blocked: the tab just isn't remembered
	}
}

function saved_tab() {
	try {
		return localStorage.getItem(TAB_KEY) === "recent_visits" ? "recent_visits" : "follow_ups";
	} catch (e) {
		return "follow_ups";
	}
}

function greeting() {
	const h = new Date().getHours();
	return h < 12 ? __("Good morning") : h < 17 ? __("Good afternoon") : __("Good evening");
}

function due_badge(f) {
	if (f.state === "overdue") return `<span class="tp-badge overdue">${__("{0}d overdue", [-f.days])}</span>`;
	if (f.state === "today") return `<span class="tp-badge today">${__("Today")}</span>`;
	if (f.days == null) return `<span class="tp-badge">${__("No date")}</span>`;
	const cls = f.state === "week" ? "week" : "";
	return `<span class="tp-badge ${cls}">${f.days === 1 ? __("Tomorrow") : __("in {0}d", [f.days])}</span>`;
}

function render_follow_ups() {
	const list = root.querySelector('[data-list="follow_ups"]');
	if (!data.follow_ups.length) {
		list.innerHTML = `<div class="tp-empty">${__("All caught up — no open follow-ups.")}</div>`;
		return;
	}
	list.innerHTML = data.follow_ups
		.map((f) => {
			const sub = [f.action, f.principal, f.owner].filter(Boolean).map(esc).join(" · ");
			return `<div class="tp-row" data-visit="${esc(f.visit)}">
				${due_badge(f)}
				<div class="tp-row-main">
					<div class="tp-row-title">${esc(f.customer_name)}</div>
					<div class="tp-row-sub">${sub || esc(f.visit)}</div>
				</div>
				<button class="btn btn-xs btn-default tp-done" data-done="${esc(f.todo)}" title="${__("Mark this follow-up as done")}">✓ ${__("Done")}</button>
			</div>`;
		})
		.join("");
	if (data.follow_ups_total > data.follow_ups.length) {
		list.insertAdjacentHTML(
			"beforeend",
			`<div class="tp-empty"><a class="tp-link" data-open="all_follow_ups">${__("+ {0} more", [
				data.follow_ups_total - data.follow_ups.length,
			])}</a></div>`
		);
	}
}

function render_visits() {
	const v = data.visits;
	let trend = __("<b>{0}</b> visits this month", [v.this_month]);
	if (v.last_month_to_date) {
		const pct = Math.round(((v.this_month - v.last_month_to_date) / v.last_month_to_date) * 100);
		const cls = pct >= 0 ? "tp-up" : "tp-down";
		trend += ` · <span class="${cls}">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct)}%</span> ${__("vs same time last month")}`;
	}
	root.querySelector(".tp-trend").innerHTML = trend;

	const list = root.querySelector('[data-list="recent_visits"]');
	if (!data.recent_visits.length) {
		list.innerHTML = `<div class="tp-empty">${__("No visits yet. Use + New Visit to log one.")}</div>`;
		return;
	}
	list.innerHTML = data.recent_visits
		.map((r) => {
			const status = r.docstatus === 0 ? "Draft" : r.lead_status;
			const sub = [frappe.datetime.str_to_user(r.visit_date), r.visit_purpose, r.principal, data.team ? r.employee_name : null]
				.filter(Boolean)
				.map(esc)
				.join(" · ");
			return `<div class="tp-row" data-visit="${esc(r.name)}">
				<div class="tp-row-main">
					<div class="tp-row-title">${esc(r.customer_name)}</div>
					<div class="tp-row-sub">${sub}</div>
				</div>
				<span class="tp-pill ${esc(status)}">${esc(__(status))}</span>
			</div>`;
		})
		.join("");
}

function render() {
	root.querySelector(".tp-hello").textContent = `${greeting()}, ${data.user_name}`;
	root.querySelector(".tp-sub").textContent = `${moment(data.today).format("dddd, D MMMM YYYY")} · ${
		data.team ? __("Showing the whole team") : __("Showing your work")
	}`;
	for (const [key, value] of Object.entries(data.counts)) {
		const el = root.querySelector(`[data-count="${key}"]`);
		el.textContent = value;
		el.closest(".tp-tile").classList.toggle("tp-zero", !value);
	}
	render_follow_ups();
	render_visits();

	// Tab badges: open follow-ups (red when some are overdue) and visits shown
	const fu = root.querySelector('[data-tab-count="follow_ups"]');
	fu.textContent = data.follow_ups_total || "";
	fu.classList.toggle("alert", data.counts.overdue > 0);
	root.querySelector('[data-tab-count="recent_visits"]').textContent = data.recent_visits.length || "";
}

function load() {
	frappe.call({
		method: "techpark.dashboard.get_today",
		callback: (r) => {
			data = r.message;
			render();
		},
	});
}

// Where each tile / "View all" link goes
function open_list(key) {
	const mine = data.team ? {} : { allocated_to: frappe.session.user };
	const routes = {
		overdue: ["ToDo", { reference_type: "Daily Visit Report", status: "Open", date: ["<", data.today], ...mine }],
		due_today: ["ToDo", { reference_type: "Daily Visit Report", status: "Open", date: data.today, ...mine }],
		all_follow_ups: ["ToDo", { reference_type: "Daily Visit Report", status: "Open", ...mine }],
		stale_prospects: ["TP Customer", { customer_status: "Prospect", prospect_since: ["<=", data.prospect_cutoff] }],
		all_visits: ["Daily Visit Report", data.team ? {} : { visited_by: frappe.session.user }],
	};
	const [doctype, filters] = routes[key];
	frappe.set_route("List", doctype, filters);
}

root.addEventListener("click", (e) => {
	const tab = e.target.closest("[data-tab]");
	if (tab) {
		show_tab(tab.dataset.tab);
		return;
	}
	const done = e.target.closest("[data-done]");
	if (done) {
		e.stopPropagation();
		done.disabled = true;
		frappe.call({
			method: "techpark.dashboard.close_follow_up",
			args: { todo: done.dataset.done },
			callback: () => {
				frappe.show_alert({ message: __("Follow-up marked as done"), indicator: "green" });
				load();
			},
			error: () => (done.disabled = false),
		});
		return;
	}
	const target = e.target.closest("[data-new], [data-open], [data-visit]");
	if (!target || !data) return;
	if (target.dataset.new) frappe.new_doc(target.dataset.new);
	else if (target.dataset.open) open_list(target.dataset.open);
	else if (target.dataset.visit) frappe.set_route("Form", "Daily Visit Report", target.dataset.visit);
});

show_tab(saved_tab());
load();
