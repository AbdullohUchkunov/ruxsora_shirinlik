frappe.pages["supplier-dashboard"].on_page_load = function (wrapper) {
	new ext_accounts.ui.SupplierDashboardPage(wrapper);
};

frappe.provide("ext_accounts.ui");

ext_accounts.ui.SupplierDashboardPage = class SupplierDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Панель контрагентов"),
			single_column: true,
		});
		this.state = {
			year: null,
			month: null,
			view: "supplier",
			party: null,
		};
		this.monthLabels = {
			Январь: "Янв",
			Февраль: "Фев",
			Март: "Мар",
			Апрель: "Апр",
			Май: "Май",
			Июнь: "Июн",
			Июль: "Июл",
			Август: "Авг",
			Сентябрь: "Сен",
			Октябрь: "Окт",
			Ноябрь: "Ноя",
			Декабрь: "Дек",
		};

		this.make_layout();
		this.bind_events();
		this.load_context();
	}

	make_layout() {
		this.wrapper.find(".layout-main-section-wrapper").addClass("supplier-dashboard-layout");
		this.wrapper.find(".page-head").addClass("supplier-dashboard-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="supplier-dashboard-screen">
				<div class="supplier-dashboard-shell">
					<header class="supplier-dashboard-header">
						<div class="supplier-dashboard-brand">
							<div class="supplier-dashboard-logo" data-region="logo">S</div>
							<div class="supplier-dashboard-brand-copy">
								<div class="supplier-dashboard-title">КОНТРАГЕНТЫ</div>
								<div class="supplier-dashboard-subtitle" data-region="company"></div>
							</div>
						</div>
						<div class="supplier-dashboard-info">i</div>
					</header>
					<div class="supplier-dashboard-filters">
						<div class="supplier-dashboard-filter-label">ФИЛЬТР ГОДА</div>
						<div class="supplier-dashboard-year-select">
							<button class="supplier-dashboard-select" type="button" data-year-toggle aria-expanded="false">
								<span data-region="selected-year">...</span>
								<span class="supplier-dashboard-chevron"></span>
							</button>
							<div class="supplier-dashboard-year-menu" data-region="years"></div>
						</div>
						<div class="supplier-dashboard-filter-label">ФИЛЬТР МЕСЯЦА</div>
						<div class="supplier-dashboard-month-grid" data-region="months"></div>
					</div>
					<div class="supplier-dashboard-view-switch" data-region="views"></div>
					<div class="supplier-dashboard-body">
						<aside class="supplier-dashboard-kpis" data-region="kpis"></aside>
						<section class="supplier-dashboard-table-panel">
							<div class="supplier-dashboard-table-meta" data-region="period"></div>
							<div class="supplier-dashboard-table-wrap" data-region="table"></div>
						</section>
					</div>
				</div>
			</div>
		`);

		this.setup_dashboard_sidebar("supplier-dashboard");

		this.$company = this.page.main.find('[data-region="company"]');
		this.$logo = this.page.main.find('[data-region="logo"]');
		this.$period = this.page.main.find('[data-region="period"]');
		this.$selectedYear = this.page.main.find('[data-region="selected-year"]');
		this.$years = this.page.main.find('[data-region="years"]');
		this.$months = this.page.main.find('[data-region="months"]');
		this.$views = this.page.main.find('[data-region="views"]');
		this.$yearSelect = this.page.main.find(".supplier-dashboard-year-select");
		this.$kpis = this.page.main.find('[data-region="kpis"]');
		this.$table = this.page.main.find('[data-region="table"]');
	}

	setup_dashboard_sidebar(route, attempt = 0) {
		if (!document.querySelector('link[href="/assets/ext_accounts/css/dashboard_navigation.css"]')) {
			$(`<link rel="stylesheet" href="/assets/ext_accounts/css/dashboard_navigation.css">`).appendTo("head");
		}

		if (window.ext_accounts && ext_accounts.ui && ext_accounts.ui.setupDashboardSidebar) {
			ext_accounts.ui.setupDashboardSidebar({
				page: this.page,
				route,
			});
			return;
		}

		if (attempt === 0 && window.frappe && frappe.require) {
			frappe.require("/assets/ext_accounts/js/dashboard_navigation.js", () => this.setup_dashboard_sidebar(route, attempt + 1));
			return;
		}

		if (attempt < 30) {
			setTimeout(() => this.setup_dashboard_sidebar(route, attempt + 1), 100);
		}
	}

	bind_events() {
		this.page.main.on("click", "[data-year-toggle]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const isOpen = this.$yearSelect.hasClass("is-open");
			this.$yearSelect.toggleClass("is-open", !isOpen);
			$(e.currentTarget).attr("aria-expanded", String(!isOpen));
		});

		$(document)
			.off("click.supplier-dashboard-year-menu")
			.on("click.supplier-dashboard-year-menu", (e) => {
				if (!$(e.target).closest(".supplier-dashboard-year-select").length) {
					this.$yearSelect.removeClass("is-open");
					this.page.main.find("[data-year-toggle]").attr("aria-expanded", "false");
				}
			});
	}

	load_context(filters = {}) {
		this.render_loading();

		frappe.call({
			method: "ext_accounts.ruxsora_app.page.supplier_dashboard.supplier_dashboard.get_dashboard_context",
			args: {
				year: Object.prototype.hasOwnProperty.call(filters, "year") ? filters.year : this.state.year,
				month: Object.prototype.hasOwnProperty.call(filters, "month") ? filters.month : this.state.month,
				view: Object.prototype.hasOwnProperty.call(filters, "view") ? filters.view : this.state.view,
				party: Object.prototype.hasOwnProperty.call(filters, "party") ? filters.party : this.state.party,
			},
			callback: (r) => {
				this.context = r.message || {};
				this.state = { ...(this.context.default_filters || {}) };
				this.render();
			},
		});
	}

	render() {
		const companyName = this.context.company_name || __("Компания");
		this.$company.text(companyName);
		this.$logo.text((companyName || "S").trim().slice(0, 1).toUpperCase());
		const selectedPartyName = this.context.selected_party_name;
		this.$period.text(
			selectedPartyName ? `Период: ${this.context.period_label || ""} • ${this.context.columns?.party_label || ""}: ${selectedPartyName}` : `Период: ${this.context.period_label || ""}`
		);
		this.render_filters();
		this.render_views();
		this.render_kpis();
		this.render_table();
	}

	render_filters() {
		this.$selectedYear.text(this.state.year || "...");
		this.$years.html(
			(this.context.years || [])
				.map(
					(year) => `
						<button class="supplier-dashboard-year-option ${year === this.state.year ? "is-active" : ""}" data-year="${year}">
							${frappe.utils.escape_html(year)}
						</button>
					`
				)
				.join("")
		);

		this.$months.html(
			(this.context.months || [])
				.map(
					(month) => `
						<button class="supplier-dashboard-month ${month === this.state.month ? "is-active" : ""}" data-month="${month}">
							${frappe.utils.escape_html(this.monthLabels[month] || month)}
						</button>
					`
				)
				.join("")
		);

		this.$years.find("[data-year]").on("click", (e) => {
			this.$yearSelect.removeClass("is-open");
			this.page.main.find("[data-year-toggle]").attr("aria-expanded", "false");
			this.load_context({
				year: String($(e.currentTarget).data("year")),
				party: null,
			});
		});

		this.$months.find("[data-month]").on("click", (e) => {
			const month = String($(e.currentTarget).data("month"));
			this.load_context({
				month: month === this.state.month ? null : month,
				party: null,
			});
		});
	}

	render_views() {
		const view = this.state.view || "supplier";
		this.$views.html(`
			<div class="supplier-dashboard-view-chip-group">
				<button class="supplier-dashboard-view-chip ${view === "client" ? "is-active" : ""}" data-view="client">${__("Клиенты")}</button>
				<button class="supplier-dashboard-view-chip ${view === "supplier" ? "is-active" : ""}" data-view="supplier">${__("Поставщики")}</button>
			</div>
		`);

		this.$views.find("[data-view]").on("click", (e) => {
			const nextView = String($(e.currentTarget).data("view") || "supplier");
			this.load_context({
				view: nextView,
				party: null,
			});
		});
	}

	render_kpis() {
		const kpis = this.context.kpis || {};
		const byCurrency = Array.isArray(kpis.by_currency) ? kpis.by_currency : [];
		const cards = byCurrency.length
			? byCurrency.flatMap((row) => [
					{ value: row.sum_prepayment, label: `Предоплата ${row.currency}`, kind: "prepayment", currency: row.currency },
					{ value: row.sum_debt, label: `Долг ${row.currency}`, kind: "debt", currency: row.currency },
			  ])
			: [
					{ value: kpis.sum_prepayment, label: "Предоплата", kind: "prepayment", currency: this.context.company_currency || "USD" },
					{ value: kpis.sum_debt, label: "Долг", kind: "debt", currency: this.context.company_currency || "USD" },
			  ];

		this.$kpis.html(
			cards
				.map(
					(card) => `
						<div class="supplier-dashboard-kpi-card">
							<div class="supplier-dashboard-kpi-value">${this.formatKpi(card.value, card.kind, card.currency)}</div>
							<div class="supplier-dashboard-kpi-label">${card.label}</div>
						</div>
					`
				)
				.join("")
		);
	}

	render_table() {
		const rows = this.context.rows || [];
		const columns = this.context.columns || {};

		if (!rows.length) {
			this.$table.html(`<div class="supplier-dashboard-empty">${__("Данные не найдены.")}</div>`);
			return;
		}

		const grouped = rows.reduce((accumulator, row) => {
			const key = String(row.currency || this.context.company_currency || "USD");
			if (!accumulator[key]) {
				accumulator[key] = [];
			}
			accumulator[key].push(row);
			return accumulator;
		}, {});

		const currencyOrder = Object.keys(grouped).sort((a, b) => (a === "USD" ? -1 : b === "USD" ? 1 : a.localeCompare(b)));

		const tableRows = currencyOrder
			.map((currency) => {
				const currencyRows = grouped[currency] || [];
				const total = currencyRows.reduce(
					(accumulator, row) => {
						accumulator.opening += Number(row.opening || 0);
						accumulator.inflow += Number(row.inflow || 0);
						accumulator.kg += Number(row.kg || 0);
						accumulator.cash_payment += Number(row.cash_payment || 0);
						accumulator.bank_payment += Number(row.bank_payment || 0);
						accumulator.sum_balance += Number(row.sum_balance || 0);
						return accumulator;
					},
					{ opening: 0, inflow: 0, kg: 0, cash_payment: 0, bank_payment: 0, sum_balance: 0 }
				);

				return `
					<tr class="supplier-dashboard-currency-row">
						<td class="is-text" colspan="8">
							<div class="supplier-dashboard-currency-banner">
								<span class="supplier-dashboard-currency-pill">${frappe.utils.escape_html(currency)}</span>
								<span>${__("Итого")}: <strong>${this.formatMoney(total.sum_balance, currency)}</strong></span>
							</div>
						</td>
					</tr>
					${currencyRows
						.map(
							(row) => `
								<tr>
									<td class="is-text">
										<button
											type="button"
											class="supplier-dashboard-party-link ${row.party === this.state.party ? "is-active" : ""}"
											data-party="${frappe.utils.escape_html(row.party || "")}"
										>
											${frappe.utils.escape_html(row.party_name || "")}
										</button>
									</td>
									<td class="is-text">
										<span class="supplier-dashboard-currency-tag">${frappe.utils.escape_html(row.currency || currency)}</span>
									</td>
									<td>${this.formatMoney(row.opening, row.currency || currency)}</td>
									<td>${this.formatMoney(row.inflow, row.currency || currency)}</td>
									<td>${this.formatKg(row.kg)}</td>
									<td>${this.formatMoney(row.cash_payment, row.currency || currency)}</td>
									<td>${this.formatMoney(row.bank_payment, row.currency || currency)}</td>
									<td class="${row.sum_balance < 0 ? "is-negative" : ""}">${this.formatMoney(row.sum_balance, row.currency || currency)}</td>
								</tr>
							`
						)
						.join("")}
					<tr class="supplier-dashboard-currency-total">
						<td class="is-text">${__("Subtotal")}</td>
						<td class="is-text">${frappe.utils.escape_html(currency)}</td>
						<td>${this.formatMoney(total.opening, currency)}</td>
						<td>${this.formatMoney(total.inflow, currency)}</td>
						<td>${this.formatKg(total.kg)}</td>
						<td>${this.formatMoney(total.cash_payment, currency)}</td>
						<td>${this.formatMoney(total.bank_payment, currency)}</td>
						<td class="${total.sum_balance < 0 ? "is-negative" : ""}">${this.formatMoney(total.sum_balance, currency)}</td>
					</tr>
				`;
			})
			.join("");

		this.$table.html(`
			<table class="supplier-dashboard-table">
				<thead>
					<tr>
						<th class="is-text">${frappe.utils.escape_html(columns.party_label || "Контрагент")}</th>
						<th class="is-text">${frappe.utils.escape_html(columns.currency_label || "Валюта")}</th>
						<th>${frappe.utils.escape_html("Начало")}</th>
						<th>${frappe.utils.escape_html(columns.inflow_label || "Приход")}</th>
						<th>${frappe.utils.escape_html(columns.kg_label || "KG")}</th>
						<th>${frappe.utils.escape_html(columns.cash_payment_label || "Оплата наличными")}</th>
						<th>${frappe.utils.escape_html(columns.bank_payment_label || "Оплата банком")}</th>
						<th>${frappe.utils.escape_html(columns.balance_label || "Сум остаток")}</th>
					</tr>
				</thead>
				<tbody>
					${tableRows}
				</tbody>
			</table>
		`);

		this.$table.find("[data-party]").on("click", (e) => {
			const party = String($(e.currentTarget).data("party") || "");
			this.load_context({
				party: party === this.state.party ? null : party,
			});
		});
	}

	formatMoney(value, currency) {
		if (value === undefined || value === null || value === "") {
			return "";
		}

		const numeric = Number(value || 0);
		const decimals = currency === "USD" ? 2 : 0;
		const formatted = Math.abs(numeric).toLocaleString("en-US", {
			minimumFractionDigits: decimals,
			maximumFractionDigits: decimals,
		});
		const suffix = currency || this.context.company_currency || "USD";
		return numeric < 0 ? `-${formatted} ${suffix}` : `${formatted} ${suffix}`;
	}

	formatKg(value) {
		if (value === undefined || value === null || value === "") {
			return "";
		}

		const numeric = Number(value || 0);
		const formatted = Math.abs(numeric).toLocaleString("en-US", {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		});
		return numeric < 0 ? `-${formatted} kg` : `${formatted} kg`;
	}

	formatKpi(value, kind, currency) {
		if (!value) {
			return "(Пусто)";
		}

		return kind === "prepayment" ? `-${this.formatMoney(value, currency || "USD")}` : this.formatMoney(value, currency || "USD");
	}

	render_loading() {
		const loadingMarkup = `<div class="supplier-dashboard-empty">${__("Загрузка...")}</div>`;
		this.$period.html("");
		this.$views.html("");
		this.$kpis.html(loadingMarkup);
		this.$table.html(loadingMarkup);
	}
};
