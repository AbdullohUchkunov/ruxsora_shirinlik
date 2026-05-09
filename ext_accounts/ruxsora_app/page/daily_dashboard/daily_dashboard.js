frappe.pages["daily-dashboard"].on_page_load = function (wrapper) {
	new ext_accounts.ui.DailyDashboardPage(wrapper);
};

frappe.provide("ext_accounts.ui");

ext_accounts.ui.DailyDashboardPage = class DailyDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Ежедневная панель"),
			single_column: true,
		});

		this.state = {
			year: null,
			month: null,
			client: null,
			day: null,
		};
		this.clientListHeight = null;

		this.make_layout();
		this.bind_events();
		this.load_context();
	}

	make_layout() {
		this.wrapper.find(".layout-main-section-wrapper").addClass("daily-dashboard-layout");
		this.wrapper.find(".page-head").addClass("daily-dashboard-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="daily-dashboard-screen">
				<div class="daily-dashboard-shell">
					<div class="daily-dashboard-topbar">
						<div class="daily-dashboard-brand">
							<div class="daily-dashboard-logo">PM</div>
							<div class="daily-dashboard-title-block">
								<div class="daily-dashboard-title-primary" data-region="title-primary"></div>
								<div class="daily-dashboard-title-secondary" data-region="title-secondary"></div>
							</div>
						</div>
						<div class="daily-dashboard-years" data-region="years"></div>
						<div class="daily-dashboard-info">i</div>
					</div>
					<div class="daily-dashboard-months" data-region="months"></div>
					<div class="daily-dashboard-clients" data-region="clients"></div>
					<div class="daily-dashboard-content">
						<div class="daily-dashboard-calendar-panel">
							<div class="daily-dashboard-calendar-title" data-region="calendar-title"></div>
							<div class="daily-dashboard-calendar-weekdays" data-region="weekdays"></div>
							<div class="daily-dashboard-calendar-grid" data-region="calendar"></div>
						</div>
						<div class="daily-dashboard-table-panel">
							<div class="daily-dashboard-table-wrap" data-region="table"></div>
						</div>
					</div>
				</div>
			</div>
		`);

		this.setup_dashboard_sidebar("daily-dashboard");

		this.$titlePrimary = this.page.main.find('[data-region="title-primary"]');
		this.$titleSecondary = this.page.main.find('[data-region="title-secondary"]');
		this.$years = this.page.main.find('[data-region="years"]');
		this.$months = this.page.main.find('[data-region="months"]');
		this.$clients = this.page.main.find('[data-region="clients"]');
		this.$content = this.page.main.find(".daily-dashboard-content");
		this.$calendarPanel = this.page.main.find(".daily-dashboard-calendar-panel");
		this.$tablePanel = this.page.main.find(".daily-dashboard-table-panel");
		this.$calendarTitle = this.page.main.find('[data-region="calendar-title"]');
		this.$weekdays = this.page.main.find('[data-region="weekdays"]');
		this.$calendar = this.page.main.find('[data-region="calendar"]');
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
		$(window).on("resize.daily-dashboard", () => this.sync_panel_heights());
	}

	load_context(filters = {}) {
		frappe.call({
			method: "ext_accounts.ruxsora_app.page.daily_dashboard.daily_dashboard.get_dashboard_context",
			args: {
				year: filters.year || this.state.year,
				month: filters.month || this.state.month,
				client: Object.prototype.hasOwnProperty.call(filters, "client") ? filters.client : this.state.client,
				day: Object.prototype.hasOwnProperty.call(filters, "day") ? filters.day : this.state.day,
			},
			callback: (r) => {
				this.context = r.message || {};
				this.state = { ...(this.context.default_filters || {}) };
				this.render();
			},
		});
	}

	render() {
		this.$titlePrimary.text(this.context.title_primary || "");
		this.$titleSecondary.text(this.context.title_secondary || "");
		this.render_years();
		this.render_months();
		this.render_clients();
		this.render_calendar();
		this.render_table();
		this.sync_panel_heights();
	}

	render_years() {
		const years = this.context.years || [];
		this.$years.html(
			years
				.map(
					(year) => `
						<button class="daily-dashboard-chip daily-dashboard-chip--year ${year === this.state.year ? "is-active" : ""}" data-year="${year}">
							${frappe.utils.escape_html(year)}
						</button>
					`
				)
				.join("")
		);

		this.$years.find("[data-year]").on("click", (e) => {
			this.load_context({
				year: String($(e.currentTarget).data("year")),
				client: null,
				day: null,
			});
		});
	}

	render_months() {
		const months = this.context.months || [];
		this.$months.html(
			months
				.map(
					(month) => `
						<button class="daily-dashboard-chip daily-dashboard-chip--month ${month.key === this.state.month ? "is-active" : ""}" data-month="${month.key}">
							${frappe.utils.escape_html(month.label)}
						</button>
					`
				)
				.join("")
		);

		this.$months.find("[data-month]").on("click", (e) => {
			this.load_context({
				month: String($(e.currentTarget).data("month")),
				client: null,
				day: null,
			});
		});
	}

	render_clients() {
		const clients = this.context.clients || [];
		this.$clients.html(
			clients
				.map(
					(client) => `
						<button class="daily-dashboard-chip daily-dashboard-chip--client ${client === this.state.client ? "is-active" : ""}" data-client="${frappe.utils.escape_html(
							client
						)}">
							${frappe.utils.escape_html(client)}
						</button>
					`
				)
				.join("")
		);

		if (!this.clientListHeight) {
			this.clientListHeight = Math.ceil(this.$clients.outerHeight() || 0);
		}
		if (this.clientListHeight) {
			this.$clients.css("height", `${this.clientListHeight}px`);
		}

		this.$clients.find("[data-client]").on("click", (e) => {
			const client = String($(e.currentTarget).data("client"));
			this.load_context({
				client: client === this.state.client ? null : client,
			});
		});
	}

	render_calendar() {
		const date = this.getActiveDate();
		const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
		const values = this.getCalendarValues();
		const firstDayOffset = (date.getDay() + 6) % 7;
		const lastDay = (this.context.calendar_meta || {}).days_in_month || new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
		const cells = [];

		for (let index = 0; index < firstDayOffset; index += 1) {
			cells.push('<div class="daily-dashboard-calendar-cell is-empty"></div>');
		}

		for (let day = 1; day <= lastDay; day += 1) {
			const value = values[day] || null;
			cells.push(`
				<button
					type="button"
					class="daily-dashboard-calendar-cell ${value ? this.getHeatClass(value, values) : "is-blank"} ${day === date.getDate() ? "is-current-day" : ""} ${day === this.state.day ? "is-active" : ""}"
					data-day="${day}"
				>
					<div class="daily-dashboard-calendar-day">${day}</div>
					<div class="daily-dashboard-calendar-value">${value ? this.formatInteger(value) : ""}</div>
				</button>
			`);
		}

		this.$calendarTitle.text((this.context.calendar_meta || {}).label || `${this.getMonthLabel(this.state.month)} ${this.state.year}`);
		this.$weekdays.html(
			weekdays
				.map((weekday) => `<div class="daily-dashboard-weekday">${frappe.utils.escape_html(weekday)}</div>`)
				.join("")
		);
		this.$calendar.html(cells.join(""));
		this.$calendar.find("[data-day]").on("click", (e) => {
			const day = Number($(e.currentTarget).data("day")) || null;
			this.load_context({
				day: day === this.state.day ? null : day,
			});
		});
	}

	render_table() {
		const rows = this.getProductRows();
		const total = this.buildTotalRow(rows);
		const headers = [
			{ label: "Товары", className: "is-text" },
			{ label: "КГ", className: "is-number" },
			{ label: "Сумма продаж", className: "is-number" },
			{ label: "Себестоимость", className: "is-number" },
			{ label: "Маржа", className: "is-number" },
			{ label: "RCP summa", className: "is-number" },
			{ label: "%", className: "is-number" },
			{ label: "ЧП", className: "is-number" },
			{ label: "Рен", className: "is-number" },
		];
		const colgroup = `
				<colgroup>
					<col style="width:320px">
					<col style="width:76px">
				${Array(7).fill('<col style="width:108px">').join("")}
			</colgroup>
		`;

		this.$table.html(`
			<div class="daily-dashboard-table-scroll">
				<table class="daily-dashboard-table">
					${colgroup}
					<thead>
						<tr>${headers
							.map((header) => `<th class="${header.className || ""}">${frappe.utils.escape_html(header.label)}</th>`)
							.join("")}</tr>
					</thead>
					<tbody>
					${rows
						.map(
							(row) => `
								<tr>
									<td class="is-text" title="${frappe.utils.escape_html(row.item)}">${frappe.utils.escape_html(row.item)}</td>
									<td class="is-number">${this.formatInteger(row.kg)}</td>
									<td class="is-number">${this.formatInteger(row.sales)}</td>
									<td class="is-number">${this.formatInteger(row.cost)}</td>
									<td class="is-number">${this.formatInteger(row.margin)}</td>
									<td class="is-number">${this.formatInteger(row.rsp)}</td>
									<td class="is-number">${this.formatPercent(row.rsp_percent)}</td>
									<td class="is-number">${this.formatInteger(row.np)}</td>
									<td class="is-number">${this.formatSignedPercent(row.profitability)}</td>
								</tr>
							`
						)
						.join("")}
					</tbody>
					<tfoot>
						<tr class="is-total">
							<td class="is-text">Итого</td>
							<td class="is-number">${this.formatInteger(total.kg)}</td>
							<td class="is-number">${this.formatInteger(total.sales)}</td>
							<td class="is-number">${this.formatInteger(total.cost)}</td>
							<td class="is-number">${this.formatInteger(total.margin)}</td>
							<td class="is-number">${this.formatInteger(total.rsp)}</td>
							<td class="is-number">${this.formatPercent(total.rsp_percent)}</td>
							<td class="is-number">${this.formatInteger(total.np)}</td>
							<td class="is-number">${this.formatSignedPercent(total.profitability)}</td>
						</tr>
					</tfoot>
				</table>
			</div>
		`);
	}

	sync_panel_heights() {
		if (!this.$calendarPanel || !this.$tablePanel) {
			return;
		}

		if (window.innerWidth <= 1200) {
			this.$tablePanel.css("height", "");
			return;
		}

		window.requestAnimationFrame(() => {
			const rect = this.$tablePanel[0].getBoundingClientRect();
			const height = window.innerHeight - rect.top - 10;
			this.$tablePanel.css("height", `${Math.max(height, 200)}px`);
		});
	}

	getActiveDate() {
		const monthIndex = (this.context.months || []).findIndex((month) => month.key === this.state.month);
		return new Date(Number(this.state.year), monthIndex >= 0 ? monthIndex : 11, 1);
	}

	getMonthLabel(monthKey) {
		const month = (this.context.months || []).find((item) => item.key === monthKey);
		return month ? month.label : "";
	}

	getCalendarValues() {
		return this.context.calendar_values || {};
	}

	getProductRows() {
		return this.context.product_rows || [];
	}

	buildTotalRow(rows) {
		const total = rows.reduce(
			(accumulator, row) => {
				accumulator.kg += row.kg;
				accumulator.sales += row.sales;
				accumulator.cost += row.cost;
				accumulator.margin += row.margin;
				accumulator.rsp += row.rsp || 0;
				accumulator.np += row.np;
				return accumulator;
			},
			{ kg: 0, sales: 0, cost: 0, margin: 0, rsp: 0, np: 0 }
		);

		total.rsp_percent = total.margin ? (total.rsp / total.margin) * 100 : 0;
		total.profitability = total.sales ? (total.margin / total.sales) * 100 : 0;
		total.np_profitability = total.sales ? (total.np / total.sales) * 100 : 0;
		return total;
	}

	getHeatClass(value, values) {
		const numericValues = Object.values(values).filter(Boolean);
		const max = Math.max(...numericValues, 1);
		const ratio = value / max;

		if (ratio >= 0.85) return "heat-5";
		if (ratio >= 0.65) return "heat-4";
		if (ratio >= 0.45) return "heat-3";
		if (ratio >= 0.2) return "heat-2";
		return "heat-1";
	}

	formatInteger(value) {
		const sign = value < 0 ? "-" : "";
		const numeric = Math.abs(Math.round(value));
		return `${sign}${String(numeric).replace(/\B(?=(\d{3})+(?!\d))/g, " ")}`;
	}

	formatPercent(value) {
		return `${this.formatDecimal(value)}%`;
	}

	formatSignedPercent(value) {
		return `${value < 0 ? "-" : ""}${this.formatDecimal(Math.abs(value))}%`;
	}

	formatDecimal(value) {
		return Number(value || 0).toFixed(1).replace(".", ",");
	}
};
