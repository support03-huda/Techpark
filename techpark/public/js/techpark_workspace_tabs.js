(function () {
	const WORKSPACE_NAME = "TechPark";
	const STORAGE_KEY = "techpark.dashboard.active_tab";

	const tabs = [
		{ key: "overview", label: "Overview", icon: "layout-dashboard" },
		{ key: "visits", label: "Visits & Leads", icon: "map-pin" },
		{ key: "customers", label: "Customers", icon: "users" },
		{ key: "expenses", label: "Expenses", icon: "wallet" },
	];

	let enhance_timer = null;
	let observer = null;

	function is_techpark_workspace() {
		const route = frappe.get_route ? frappe.get_route() : [];

		if (route[0] !== "Workspaces") {
			return false;
		}

		return route[route.length - 1] === WORKSPACE_NAME || frappe.workspace?._page?.name === WORKSPACE_NAME;
	}

	function get_workspace_content() {
		let content = frappe.workspace?.content || frappe.workspace?._page?.content || [];

		if (typeof content === "string") {
			try {
				content = JSON.parse(content);
			} catch (e) {
				content = [];
			}
		}

		return Array.isArray(content) ? content : [];
	}

	function strip_html(html) {
		const div = document.createElement("div");
		div.innerHTML = html || "";
		return (div.textContent || div.innerText || "").replace(/\s+/g, " ").trim();
	}

	function get_header_tab(block) {
		const text = strip_html(block?.data?.text);

		if (text.includes("Visits & Leads")) return "visits";
		if (text === "Customers") return "customers";
		if (text === "Expenses") return "expenses";

		return "overview";
	}

	// Every block belongs to the tab of the section header above it, so the same
	// chart / card can be shown on Overview and on its own tab.
	function get_block_tab(block, current_tab) {
		if (block?.type === "header") return get_header_tab(block);

		return current_tab;
	}

	function get_tab_map(content) {
		let current_tab = "overview";

		return content.map((block) => {
			const tab = get_block_tab(block, current_tab);

			if (block.type !== "spacer") {
				current_tab = tab;
			}

			return tab;
		});
	}

	function get_active_tab() {
		const saved = localStorage.getItem(STORAGE_KEY);
		return tabs.some((tab) => tab.key === saved) ? saved : tabs[0].key;
	}

	function set_active_tab(active_tab, $wrapper) {
		$wrapper.find(".tp-dashboard-tab").each(function () {
			const is_active = this.dataset.tab === active_tab;
			this.classList.toggle("active", is_active);
			this.setAttribute("aria-selected", is_active ? "true" : "false");
		});

		$wrapper.find("[data-tp-dashboard-tab]").each(function () {
			this.classList.toggle("tp-dashboard-hidden", this.dataset.tpDashboardTab !== active_tab);
		});

		requestAnimationFrame(() => {
			window.dispatchEvent(new Event("resize"));
		});
	}

	function make_tab_bar($redactor, active_tab) {
		let $tabs = $redactor.prev(".tp-dashboard-tabs");

		if (!$tabs.length) {
			$tabs = $('<div class="tp-dashboard-tabs" role="tablist"></div>');
			$tabs.insertBefore($redactor);
		}

		$tabs.empty();

		tabs.forEach((tab) => {
			const icon = frappe.utils?.icon ? frappe.utils.icon(tab.icon, "sm") : "";
			const $button = $(
				`<button class="btn btn-default tp-dashboard-tab" type="button" role="tab" data-tab="${tab.key}">
					<span class="tp-dashboard-tab-icon">${icon}</span>
					<span>${__(tab.label)}</span>
				</button>`
			);

			$button.on("click", () => {
				localStorage.setItem(STORAGE_KEY, tab.key);
				set_active_tab(tab.key, $redactor.parent());
			});

			$tabs.append($button);
		});

		set_active_tab(active_tab, $redactor.parent());
	}

	function cleanup() {
		if (observer) {
			observer.disconnect();
			observer = null;
		}

		$(".tp-dashboard-tabs").remove();
		$("[data-tp-dashboard-tab]").each(function () {
			this.classList.remove("tp-dashboard-hidden");
			this.removeAttribute("data-tp-dashboard-tab");
		});
	}

	function watch_workspace($redactor) {
		if (observer) {
			observer.disconnect();
		}

		observer = new MutationObserver(() => schedule_enhancement(3));
		observer.observe($redactor[0], { childList: true });
	}

	function enhance_workspace() {
		if (!is_techpark_workspace()) {
			cleanup();
			return true;
		}

		const $wrapper = $(frappe.workspace?.wrapper || document);
		const $redactor = $wrapper.find(".codex-editor__redactor").first();
		const content = get_workspace_content();
		const $blocks = $redactor.children(".ce-block");

		if (!$redactor.length || !content.length || !$blocks.length) {
			return false;
		}

		if ($wrapper.find(".workspace-body").hasClass("edit-mode")) {
			cleanup();
			return true;
		}

		const tab_map = get_tab_map(content);

		$blocks.each(function (index) {
			this.dataset.tpDashboardTab = tab_map[index] || "overview";
		});

		make_tab_bar($redactor, get_active_tab());
		watch_workspace($redactor);

		return true;
	}

	function schedule_enhancement(retries = 8) {
		clearTimeout(enhance_timer);

		enhance_timer = setTimeout(() => {
			if (!enhance_workspace() && retries > 0) {
				schedule_enhancement(retries - 1);
			}
		}, 150);
	}

	$(document).on("page-change", () => schedule_enhancement());

	if (frappe.router?.on) {
		frappe.router.on("change", () => schedule_enhancement());
	}

	frappe.after_ajax(() => schedule_enhancement());
	$(schedule_enhancement);
})();
