frappe.provide("ext_accounts.ui");

(() => {
	const MENU_OPEN_KEY = "ext_accounts:dashboard-sidebar:menu-open";
	const DRAWER_OPEN_KEY = "ext_accounts:dashboard-sidebar:drawer-open";
	const SCOPE_CLASS = "custom-dashboard-scope";
	const FALLBACK_MENU_ITEMS = [
		{ label: __("Main dashboard"), route: "main-dashboard" },
		{ label: __("Page dashboard"), route: "page-dashboard" },
		{ label: __("Sales dashboard"), route: "sales-dashboard" },
		{ label: __("Daily dashboard"), route: "daily-dashboard" },
		{ label: __("Supplier dashboard"), route: "supplier-dashboard" },
	];
	let dashboardItemsCache = null;

	function readBool(key, defaultValue) {
		try {
			const value = window.localStorage.getItem(key);
			return value === null ? defaultValue : value === "1";
		} catch (error) {
			return defaultValue;
		}
	}

	function writeBool(key, value) {
		try {
			window.localStorage.setItem(key, value ? "1" : "0");
		} catch (error) {
			// Ignore localStorage failures in restricted browsers.
		}
	}

	function normalizeItems(items) {
		const seen = new Set();
		return (items || [])
			.map((item) => ({
				label: item.label || item.route,
				route: item.route || item.link_to,
			}))
			.filter((item) => {
				if (!item.label || !item.route || seen.has(item.route)) {
					return false;
				}
				seen.add(item.route);
				return true;
			});
	}

	function loadDashboardItems(callback) {
		if (dashboardItemsCache) {
			callback(dashboardItemsCache);
			return;
		}

		frappe.call({
			method: "ext_accounts.ruxsora_app.dashboard_navigation.get_dashboard_links",
			callback: (response) => {
				const items = normalizeItems(response.message);
				dashboardItemsCache = items.length ? items : FALLBACK_MENU_ITEMS;
				callback(dashboardItemsCache);
			},
			error: () => {
				dashboardItemsCache = FALLBACK_MENU_ITEMS;
				callback(dashboardItemsCache);
			},
		});
	}

	function renderSidebar({ $sidebarHost, route, items }) {
		const menuOpen = window.matchMedia("(min-width: 992px)").matches ? true : readBool(MENU_OPEN_KEY, true);
		const drawerOpen = readBool(DRAWER_OPEN_KEY, false);
		const menuItems = normalizeItems(items).length ? normalizeItems(items) : FALLBACK_MENU_ITEMS;

		$sidebarHost.children(".dashboard-sidebar-shell").remove();
		$sidebarHost.addClass("has-dashboard-floating-sidebar");
		$sidebarHost.prepend(`
			<div class="dashboard-sidebar-shell ${drawerOpen ? "is-drawer-open" : ""}">
				<button class="dashboard-sidebar-backdrop" type="button" aria-label="${__("Закрыть меню")}"></button>
				<aside class="dashboard-sidebar-nav">
					<div class="dashboard-sidebar-nav-head">
						<div class="dashboard-sidebar-nav-title">${__("Dashboardlar")}</div>
						<button class="dashboard-sidebar-mobile-close" type="button" aria-label="${__("Закрыть меню")}">
							<span aria-hidden="true">&times;</span>
						</button>
					</div>
					<div class="dashboard-sidebar-group ${menuOpen ? "is-open" : ""}">
						<button class="dashboard-sidebar-group-toggle" type="button" aria-expanded="${menuOpen ? "true" : "false"}">
							<span>${__("Dashboard list")}</span>
							<span class="dashboard-sidebar-group-arrow" aria-hidden="true"></span>
						</button>
						<div class="dashboard-sidebar-items">
							${menuItems.map(
								(item) => `
									<button
										class="dashboard-sidebar-item ${item.route === route ? "is-active" : ""}"
										type="button"
										data-route="${item.route}"
									>
										<span class="dashboard-sidebar-item-dot" aria-hidden="true"></span>
										<span>${frappe.utils.escape_html(item.label)}</span>
									</button>
								`
							).join("")}
						</div>
					</div>
				</aside>
				<button class="dashboard-sidebar-mobile-toggle dashboard-sidebar-floating-toggle" type="button" aria-label="${__("Открыть меню")}">
					<span class="dashboard-sidebar-mobile-toggle-line"></span>
					<span class="dashboard-sidebar-mobile-toggle-line"></span>
					<span class="dashboard-sidebar-mobile-toggle-line"></span>
				</button>
			</div>
		`);

		const $shell = $sidebarHost.children(".dashboard-sidebar-shell").first();
		const $group = $shell.find(".dashboard-sidebar-group");
		const $items = $shell.find(".dashboard-sidebar-items");
		const $groupToggle = $shell.find(".dashboard-sidebar-group-toggle");

		const syncGroupState = (isOpen) => {
			$group.toggleClass("is-open", isOpen);
			$groupToggle.attr("aria-expanded", isOpen ? "true" : "false");
			$items.css("display", isOpen ? "flex" : "none");
			writeBool(MENU_OPEN_KEY, isOpen);
		};

		const syncDrawerState = (isOpen) => {
			$shell.toggleClass("is-drawer-open", isOpen);
			writeBool(DRAWER_OPEN_KEY, isOpen);
		};

		syncGroupState(menuOpen);
		syncDrawerState(drawerOpen);

		$groupToggle.on("click", () => {
			syncGroupState(!$group.hasClass("is-open"));
		});

		$shell.find(".dashboard-sidebar-mobile-toggle").on("click", () => {
			syncDrawerState(true);
		});

		$shell.find(".dashboard-sidebar-mobile-close, .dashboard-sidebar-backdrop").on("click", () => {
			syncDrawerState(false);
		});

		$shell.find(".dashboard-sidebar-item").on("click", (event) => {
			const targetRoute = $(event.currentTarget).data("route");
			if (!targetRoute || targetRoute === route) {
				syncDrawerState(false);
				return;
			}

			syncDrawerState(false);
			frappe.set_route(targetRoute);
		});
	}

	ext_accounts.ui.setupDashboardSidebar = function setupDashboardSidebar({ page, route }) {
		if (!page || !page.main || !route) {
			return;
		}

		const $layout = page.main.closest(".layout-main-section-wrapper");
		if (!$layout.length) {
			return;
		}

		const $pageBody = $layout.closest(".page-body");
		const $pageWrapper = page.wrapper ? $(page.wrapper) : $layout.closest(".page-wrapper");
		const $container = $layout.closest(".container");
		const $pageContainer = $layout.closest(".page-container");
		const $deskPage = $layout.closest(".desk-page");
		const $layoutSection = $layout.closest(".layout-main-section");

		$pageBody.addClass(SCOPE_CLASS);
		$pageWrapper.addClass(SCOPE_CLASS);
		$layout.addClass(SCOPE_CLASS);
		$container.addClass(SCOPE_CLASS);
		$pageContainer.addClass(SCOPE_CLASS);
		$deskPage.addClass(SCOPE_CLASS);
		$layoutSection.addClass(SCOPE_CLASS);

		const $sidebarHost = $layoutSection.length ? $layoutSection : $layout;
		renderSidebar({ $sidebarHost, route, items: dashboardItemsCache || FALLBACK_MENU_ITEMS });
		loadDashboardItems((items) => {
			renderSidebar({ $sidebarHost, route, items });
		});
	};
})();
