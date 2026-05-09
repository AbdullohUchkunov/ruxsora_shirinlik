frappe.pages["sales-dashboard"].on_page_load = function (wrapper) {
	new ext_accounts.ui.SalesDashboardPage(wrapper);
};

frappe.provide("ext_accounts.ui");

ext_accounts.ui.SalesDashboardPage = class SalesDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Панель продаж"),
			single_column: true,
		});

		this.state = {
			year: null,
			month: null,
		};

		this.make_layout();
		this.load_context();
	}

	ensure_runtime_styles() {
		if (document.getElementById("sales-dashboard-table-layout-fix")) {
			return;
		}

		const style = document.createElement("style");
		style.id = "sales-dashboard-table-layout-fix";
		style.textContent = `
			.sales-dashboard-table-panel {
				width: calc(100% - 20px) !important;
				max-width: none !important;
				margin: 0 10px !important;
				transform: none !important;
				box-sizing: border-box !important;
			}
			.sales-dashboard-table-wrap {
				max-width: 100% !important;
				overflow: auto !important;
			}
			.sales-dashboard-table {
				width: 100% !important;
				min-width: 1100px !important;
				table-layout: auto !important;
				border-collapse: collapse !important;
			}
			.sales-dashboard-table .is-text {
				min-width: 280px !important;
				text-align: left !important;
			}
			.sales-dashboard-table .is-number {
				min-width: 112px !important;
				text-align: right !important;
				white-space: nowrap !important;
			}
		`;
		document.head.appendChild(style);
	}

	make_layout() {
		this.ensure_runtime_styles();
		this.wrapper.find(".layout-main-section-wrapper").addClass("sales-dashboard-layout");
		this.wrapper.find(".page-head").addClass("sales-dashboard-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="sales-dashboard-screen">
				<div class="sales-dashboard-shell">
					<div class="sales-dashboard-filters sales-dashboard-filters--years" data-region="years"></div>
					<div class="sales-dashboard-filters sales-dashboard-filters--months" data-region="months"></div>
					<div class="sales-dashboard-table-panel">
						<div class="sales-dashboard-table-wrap" data-region="table"></div>
					</div>
				</div>
			</div>
		`);

		this.setup_dashboard_sidebar("sales-dashboard");

		this.$years = this.page.main.find('[data-region="years"]');
		this.$months = this.page.main.find('[data-region="months"]');
		this.$table = this.page.main.find('[data-region="table"]');

		this.$table.on("click", "tbody tr[data-row-index]", (event) => {
			const $row = $(event.currentTarget);
			$row.addClass("is-active").siblings("tr[data-row-index]").removeClass("is-active");
		});
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

	load_context() {
		this.render_loading();

		frappe.call({
			method: "ext_accounts.ruxsora_app.page.sales_dashboard.sales_dashboard.get_dashboard_context",
			args: {
				year: this.state.year,
				month: this.state.month,
			},
			callback: (r) => {
				this.context = r.message || {};
				this.state = { ...(this.context.default_filters || {}) };
				this.render();
			},
		});
	}

	render() {
		this.render_years();
		this.render_months();
		this.render_table();
	}

	render_years() {
		const years = this.context.years || [];
		const hasOverflow = years.length > 6;
		const wrapClass = hasOverflow ? "is-scrollable" : "is-centered";
		this.$years.html(
			`
				<div class="sales-dashboard-year-group-wrap ${wrapClass}">
					<div class="sales-dashboard-year-group">
						${years
							.map(
								(year) => `
									<button class="sales-dashboard-chip sales-dashboard-chip--year ${year === this.state.year ? "is-active" : ""}" data-year="${year}">
										${frappe.utils.escape_html(year)}
									</button>
								`
							)
							.join("")}
					</div>
				</div>
			`
		);

		this.$years.find("[data-year]").on("click", (e) => {
			this.state.year = String($(e.currentTarget).data("year"));
			this.load_context();
		});
	}

	render_months() {
		const months = this.context.months || [];
		this.$months.html(
			months
				.map(
					(month) => `
						<button class="sales-dashboard-chip sales-dashboard-chip--month ${month.key === this.state.month ? "is-active" : ""}" data-month="${month.key}">
							${frappe.utils.escape_html(month.label)}
						</button>
					`
				)
				.join("")
		);

		this.$months.find("[data-month]").on("click", (e) => {
			this.state.month = String($(e.currentTarget).data("month"));
			this.load_context();
		});
	}

	render_table() {
		const rows = this.context.product_rows || [];
		const total = this.buildTotalRow(rows);
		const headers = ["Товары", "КГ", "Сумма продаж", "Себестоимость", "Маржа", "Сумма РСП", "Рен", "Прибыль"];

		if (!rows.length) {
			this.$table.html(`
				<div class="sales-dashboard-table-empty">
					${__("За выбранный период нет проведенных счетов продаж.")}
				</div>
			`);
			return;
		}

		this.$table.html(`
			<table class="sales-dashboard-table">
				<thead>
					<tr>${headers.map((header, index) => `<th class="${index === 0 ? "is-text" : "is-number"}">${header}</th>`).join("")}</tr>
				</thead>
				<tbody>
					${rows
						.map(
							(row, index) => `
								<tr data-row-index="${index}">
									<td class="is-text">${frappe.utils.escape_html(row.item)}</td>
									<td class="is-number">${this.formatInteger(row.kg)}</td>
									<td class="is-number">${this.formatInteger(row.sales)}</td>
									<td class="is-number">${this.formatInteger(row.cost)}</td>
									<td class="is-number">${this.formatInteger(row.margin)}</td>
									<td class="is-number">${this.formatInteger(row.rsp)}</td>
									<td class="is-number">${this.formatPercent(row.margin_percent)}</td>
									<td class="is-number ${row.profit < 0 ? "is-negative" : ""}">${this.formatInteger(row.profit)}</td>
								</tr>
							`
						)
						.join("")}
					<tr class="is-total">
						<td class="is-text">Итого</td>
						<td class="is-number">${this.formatInteger(total.kg)}</td>
						<td class="is-number">${this.formatInteger(total.sales)}</td>
						<td class="is-number">${this.formatInteger(total.cost)}</td>
						<td class="is-number">${this.formatInteger(total.margin)}</td>
						<td class="is-number">${this.formatInteger(total.rsp)}</td>
						<td class="is-number">${this.formatPercent(total.margin_percent)}</td>
						<td class="is-number ${total.profit < 0 ? "is-negative" : ""}">${this.formatInteger(total.profit)}</td>
					</tr>
				</tbody>
			</table>
		`);
	}

	buildTotalRow(rows) {
		const total = rows.reduce(
			(accumulator, row) => {
				accumulator.kg += row.kg;
				accumulator.sales += row.sales;
				accumulator.cost += row.cost;
				accumulator.margin += row.margin;
				accumulator.rsp += row.rsp;
				accumulator.profit += row.profit;
				return accumulator;
			},
			{ kg: 0, sales: 0, cost: 0, margin: 0, rsp: 0, profit: 0 }
		);

		total.margin_percent = total.sales ? (total.margin / total.sales) * 100 : 0;
		return total;
	}

	formatInteger(value) {
		const sign = value < 0 ? "-" : "";
		const numeric = Math.abs(Math.round(value));
		return `${sign}${String(numeric).replace(/\B(?=(\d{3})+(?!\d))/g, " ")}`;
	}

	formatPercent(value) {
		return `${Number(value || 0).toFixed(1).replace(".", ",")}%`;
	}

	render_loading() {
		this.$table.html(`<div class="sales-dashboard-table-empty">${__("Загрузка...")}</div>`);
	}
};
