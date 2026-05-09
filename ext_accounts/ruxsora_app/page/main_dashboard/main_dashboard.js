frappe.pages["main-dashboard"].on_page_load = function (wrapper) {
	new ext_accounts.ui.MainDashboardPage(wrapper);
};

frappe.provide("ext_accounts.ui");

ext_accounts.ui.MainDashboardPage = class MainDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Main dashboard"),
			single_column: true,
		});

		this.state = {
			year: "",
			month: "",
		};
		this.months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
		this.monthLabels = {
			Jan: "Янв",
			Feb: "Фев",
			Mar: "Мар",
			Apr: "Апр",
			May: "Май",
			Jun: "Июн",
			Jul: "Июл",
			Aug: "Авг",
			Sep: "Сен",
			Oct: "Окт",
			Nov: "Ноя",
			Dec: "Дек",
		};
		this.fullMonthLabels = {
			Jan: "Январь",
			Feb: "Февраль",
			Mar: "Март",
			Apr: "Апрель",
			May: "Май",
			Jun: "Июнь",
			Jul: "Июль",
			Aug: "Август",
			Sep: "Сентябрь",
			Oct: "Октябрь",
			Nov: "Ноябрь",
			Dec: "Декабрь",
		};
		this.years = [];
		this.data = null;

		this.make_layout();
		this.bind_events();
		this.load_data();
	}

	make_layout() {
		this.wrapper.addClass("main-dashboard-page");
		this.wrapper.find(".layout-main-section-wrapper").addClass("main-dashboard-layout");
		this.wrapper.find(".layout-main-section").addClass("main-dashboard-section");
		this.wrapper.find(".page-body, .page-container, .container").addClass("main-dashboard-full-width");
		this.wrapper.find(".page-head").addClass("main-dashboard-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="mds-screen">
				<section class="mds-main">
					<div class="mds-filters">
						<div class="mds-filter-label">ФИЛЬТР ГОДА</div>
						<div class="mds-year-select">
							<button class="mds-select" type="button" data-year-toggle aria-expanded="false">
								<span data-region="selected-year">...</span>
								<span class="mds-chevron"></span>
							</button>
							<div class="mds-year-menu" data-region="year-menu"></div>
						</div>
						<div class="mds-filter-label">ФИЛЬТР МЕСЯЦА</div>
						<div class="mds-month-grid" data-region="month-grid"></div>
					</div>
					<div class="mds-content">
						<section class="mds-card mds-card--wide mds-sales-card">
							<div class="mds-card-head">
								<h2>ОБЪЕМ ПРОДАЖ (ТОННЫ)</h2>
							</div>
							<div class="mds-bar-chart" data-region="sales-chart"></div>
						</section>
						<section class="mds-card mds-card--donut">
							<div class="mds-card-head">
								<h2>ПРОДАЖА И РАСХОДЫ</h2>
							</div>
							<div data-region="margin-bonus"></div>
						</section>
						<section class="mds-card mds-average-card">
							<div data-region="average-check"></div>
						</section>
						<section class="mds-card mds-balance-card">
							<div data-region="balance-details"></div>
						</section>
						<div class="mds-stack-column">
							<section class="mds-card mds-break-card">
								<div data-region="unit-cost"></div>
							</section>
							<section class="mds-card mds-health-panel">
								<div data-region="business-health"></div>
							</section>
						</div>
						<section class="mds-card mds-returns-card">
							<h2>АНАЛИЗ ВОЗВРАТОВ</h2>
							<div class="mds-return-chart" data-region="return-chart"></div>
						</section>
						<section class="mds-card mds-profit-card">
							<div class="mds-card-head">
								<h2>ЧИСТАЯ ПРИБЫЛЬ И РЕНТАБЕЛЬНОСТЬ</h2>
								<div class="mds-legend mds-legend--compact">
									<span><i class="is-blue"></i> Чистая прибыль</span>
									<span><i class="is-green"></i> Рентабельность</span>
								</div>
							</div>
							<div class="mds-profit-chart" data-region="profit-chart"></div>
						</section>
					</div>
				</section>
			</div>
		`);

		this.setup_dashboard_sidebar("main-dashboard");

		this.$salesChart = this.page.main.find('[data-region="sales-chart"]');
		this.$returnChart = this.page.main.find('[data-region="return-chart"]');
		this.$profitChart = this.page.main.find('[data-region="profit-chart"]');
		this.$selectedYear = this.page.main.find('[data-region="selected-year"]');
		this.$yearMenu = this.page.main.find('[data-region="year-menu"]');
		this.$monthGrid = this.page.main.find('[data-region="month-grid"]');
		this.$marginBonus = this.page.main.find('[data-region="margin-bonus"]');
		this.$averageCheck = this.page.main.find('[data-region="average-check"]');
		this.$balanceDetails = this.page.main.find('[data-region="balance-details"]');
		this.$unitCost = this.page.main.find('[data-region="unit-cost"]');
		this.$businessHealth = this.page.main.find('[data-region="business-health"]');
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
		this.page.main.off(".main-dashboard");

		this.page.main.on("click.main-dashboard", "[data-year-toggle]", (event) => {
			event.stopPropagation();
			const $select = $(event.currentTarget).closest(".mds-year-select");
			const isOpen = $select.hasClass("is-open");
			$select.toggleClass("is-open", !isOpen);
			$(event.currentTarget).attr("aria-expanded", isOpen ? "false" : "true");
		});

		this.page.main.on("click.main-dashboard", "[data-year]", (event) => {
			const year = String($(event.currentTarget).data("year"));
			this.load_data({ year, month: this.state.month });
		});

		this.page.main.on("click.main-dashboard", "[data-month]", (event) => {
			const month = String($(event.currentTarget).data("month"));
			this.load_data({ year: this.state.year, month });
		});

		$(document).off("click.main-dashboard-year").on("click.main-dashboard-year", (event) => {
			if ($(event.target).closest(".mds-year-select").length) {
				return;
			}

			this.page.main.find(".mds-year-select").removeClass("is-open");
			this.page.main.find("[data-year-toggle]").attr("aria-expanded", "false");
		});
	}

	render_year_option(year) {
		return `<button class="mds-year-option ${year === this.state.year ? "is-active" : ""}" type="button" data-year="${year}">${year}</button>`;
	}

	render_month_button(month) {
		return `<button class="mds-month ${month === this.state.month ? "is-active" : ""}" type="button" data-month="${month}">${this.monthLabels[month] || month}</button>`;
	}

	render_balance_item(label, value) {
		return `
			<div class="mds-balance-item">
				<div class="mds-balance-row">
					<span>${frappe.utils.escape_html(label)}</span>
					<strong>${frappe.utils.escape_html(value)}</strong>
				</div>
			</div>
		`;
	}

	load_data(filters = {}) {
		this.show_loading();
		return frappe.call({
			method: "ext_accounts.ruxsora_app.page.main_dashboard.main_dashboard.get_dashboard_data",
			args: {
				year: filters.year || this.state.year || undefined,
				month: filters.month || this.state.month || undefined,
			},
		}).then((response) => {
			this.data = response.message || {};
			const backendFilters = this.data.filters || {};
			this.years = backendFilters.years || [];
			this.state.year = backendFilters.selected_year || "";
			this.state.month = backendFilters.selected_month || "";
			this.render();
		}).catch(() => {
			frappe.msgprint(__("Не удалось загрузить данные главной панели."));
		});
	}

	show_loading() {
		const loadingMarkup = `<div class="mds-loading">Загрузка...</div>`;
		this.$salesChart.html(loadingMarkup);
		this.$returnChart.html(loadingMarkup);
		this.$profitChart.html(loadingMarkup);
		this.$marginBonus.html(loadingMarkup);
		this.$averageCheck.html(loadingMarkup);
		this.$balanceDetails.html(loadingMarkup);
		this.$unitCost.html(loadingMarkup);
		this.$businessHealth.html(loadingMarkup);
	}

	render() {
		this.render_filters();
		this.render_sales_chart();
		this.render_returns_chart();
		this.render_margin_bonus();
		this.render_average_check();
		this.render_balance_details();
		this.render_unit_cost();
		this.render_business_health_card();
		this.render_profit_chart();
	}

	render_filters() {
		this.$selectedYear.text(this.state.year || "...");
		this.$yearMenu.html(this.years.map((year) => this.render_year_option(year)).join(""));
		this.$monthGrid.html(this.months.map((month) => this.render_month_button(month)).join(""));
	}

	render_sales_chart() {
		const salesData = this.data?.sales_volume?.series || [];
		const maxSales = Math.max(1, ...salesData.map((row) => Number(row.tons || 0)));
		this.$salesChart.html(`
			<div class="mds-bar-grid">
				${this.months
					.map((month, index) => {
						const row = salesData[index] || { tons: 0, amount_display: "" };
						return this.render_chart_bar({
							month,
							row,
							maxValue: maxSales,
							active: month === this.state.month,
							barClass: "mds-bar",
						});
					})
					.join("")}
			</div>
		`);
	}

	render_returns_chart() {
		const returnData = this.data?.returns_analysis?.series || [];
		this.$returnChart.html(`
			<div class="mds-return-table">
				<div class="mds-return-table-head">
					<span>Месяц</span>
					<span>КГ</span>
					<span>Сумма</span>
				</div>
				<div class="mds-return-table-body">
					${this.months
						.map((month, index) => {
							const row = returnData[index] || { tons_display: "", amount_display: "" };
							return `
								<div class="mds-return-table-row ${month === this.state.month ? "is-active" : ""}">
									<span>${frappe.utils.escape_html(this.fullMonthLabels[month] || month)}</span>
									<strong>${frappe.utils.escape_html(row.tons_display || "0 кг")}</strong>
									<strong>${frappe.utils.escape_html(row.amount_display || "0")}</strong>
								</div>
							`;
						})
						.join("")}
				</div>
			</div>
		`);
	}

	render_chart_bar({ month, row, maxValue, active, barClass }) {
		const tons = Number(row.tons || 0);
		const height = maxValue > 0 && tons > 0 ? Math.max((tons / maxValue) * 100, 12) : 0;

		return `
			<div class="mds-bar-item ${active ? "is-active" : ""}">
				<div class="mds-bar-ton">${row.tons_display || ""}</div>
				<div class="mds-bar-shell">
					<div class="${barClass} ${active ? "is-active" : ""} ${tons ? "" : "is-empty"}" style="height:${height}%">
						${row.amount_display ? `<span class="mds-bar-amount">${frappe.utils.escape_html(row.amount_display)}</span>` : ""}
					</div>
				</div>
				<span class="mds-bar-month">${frappe.utils.escape_html(this.monthLabels[month] || month)}</span>
			</div>
		`;
	}

	render_margin_bonus() {
		const data = this.data?.margin_bonus || {};

		const SEGS = (data.segments || []).map((segment) => ({
			label: segment.label || "",
			pct: Number(segment.percent || 0),
			amount: segment.amount_display || "0 USD",
			pctDisp: segment.percent_display || "0%",
			color: segment.color || "#2563eb",
		}));

		const W = 340, H = 252, CX = 170, CY = 126, OR = 78, IR = 50, ER = 96;
		const RIGHT_X = 278, LEFT_X = 62;
		const toRad = (deg) => (deg - 90) * Math.PI / 180;
		const pt = (r, deg) => ({ x: CX + r * Math.cos(toRad(deg)), y: CY + r * Math.sin(toRad(deg)) });
		const f = (n) => n.toFixed(2);
		const arcPath = (s, e) => {
			const a = pt(OR, s), b = pt(OR, e), c = pt(IR, e), d = pt(IR, s);
			const lg = e - s > 180 ? 1 : 0;
			return `M${f(a.x)},${f(a.y)} A${OR},${OR} 0 ${lg} 1 ${f(b.x)},${f(b.y)} L${f(c.x)},${f(c.y)} A${IR},${IR} 0 ${lg} 0 ${f(d.x)},${f(d.y)} Z`;
		};

		const absSum = SEGS.reduce((sum, seg) => sum + Math.abs(seg.pct), 0) || 1;
		let cumDeg = 0;
		const built = SEGS.map((seg) => {
			const span = (Math.abs(seg.pct) / absSum) * 360;
			const start = cumDeg;
			cumDeg += span;
			return { ...seg, start, end: cumDeg, mid: start + span / 2, span };
		});

		const callouts = built.map((seg) => {
			const elbow = pt(ER, seg.mid);
			const isRight = elbow.x >= CX;
			return { ...seg, elbow, isRight, calloutY: elbow.y };
		});
		const placeSideCallouts = (items, side) => {
			const top = 46;
			const gap = 28;
			const startY = top + Math.max(0, 3 - items.length) * (gap / 2);
			const sorted = [...items].sort((a, b) => a.elbow.y - b.elbow.y);
			sorted.forEach((item, index) => {
				item.isRight = side === "right";
				item.calloutY = startY + index * gap;
			});
		};
		placeSideCallouts(callouts.filter((seg) => seg.isRight), "right");
		placeSideCallouts(callouts.filter((seg) => !seg.isRight), "left");

		const GRAD = {
			"#dc2626": ["#fca5a5", "#dc2626", "#7f1d1d"],
			"#2563eb": ["#93c5fd", "#2563eb", "#1e3a8a"],
			"#22c55e": ["#86efac", "#22c55e", "#14532d"],
			"#f0b429": ["#fde68a", "#f0b429", "#78350f"],
		};
		const gid = (color) => `mbg${color.replace("#", "")}`;
		const defs = `<defs>${SEGS.map((seg) => {
			const [hi, mid, lo] = GRAD[seg.color] || [seg.color, seg.color, seg.color];
			return `<linearGradient id="${gid(seg.color)}" x1="${CX}" y1="${CY - OR}" x2="${CX}" y2="${CY + OR}" gradientUnits="userSpaceOnUse">
				<stop offset="0%" stop-color="${hi}"/>
				<stop offset="45%" stop-color="${mid}"/>
				<stop offset="100%" stop-color="${lo}"/>
			</linearGradient>`;
		}).join("")}</defs>`;

		const paths = callouts
			.map((seg) => {
				if (seg.span < 0.3) return "";
				const dx = (10 * Math.cos(toRad(seg.mid))).toFixed(2);
				const dy = (10 * Math.sin(toRad(seg.mid))).toFixed(2);
				const mid = pt(OR, seg.mid);
				const textX = seg.isRight ? RIGHT_X : LEFT_X;
				const anchor = seg.isRight ? "start" : "end";
				const labelX = seg.isRight ? textX + 5 : textX - 5;
				const ey = seg.calloutY.toFixed(2);
				const amtText = String(seg.amount).replace(/ USD$/, "");
				return `<g class="mds-mb-segment" style="--tx:${dx}px;--ty:${dy}px">
					<path class="mds-mb-seg-vis" d="${arcPath(seg.start, seg.end)}" fill="url(#${gid(seg.color)})"/>
					<path class="mds-mb-seg-hit" d="${arcPath(seg.start, seg.end)}" fill="transparent"/>
					<polyline class="mds-mb-callout-line" points="${mid.x.toFixed(1)},${mid.y.toFixed(1)} ${seg.elbow.x.toFixed(1)},${ey} ${textX},${ey}" fill="none" stroke="${seg.color}" stroke-width="1.3"/>
					<text class="mds-mb-callout-value" x="${labelX}" y="${(seg.calloutY + 5).toFixed(1)}" text-anchor="${anchor}" fill="${seg.color}" font-size="13" font-weight="700">${frappe.utils.escape_html(amtText)}</text>
				</g>`;
			})
			.join("");

		const centerColor = "#2563eb";
		const centerAmt = frappe.utils.escape_html(String(data.sales_amount_display || data.total_amount_display || "").replace(/ USD$/, ""));
		const svg = `<svg class="mds-mb-svg" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
			${defs}
			${paths}
			<text x="${CX}" y="${CY + 5}" text-anchor="middle" fill="${centerColor}" font-size="13" font-weight="700">${centerAmt}</text>
		</svg>`;

		const fmtAmt = (value) => frappe.utils.escape_html(String(value || "").replace(/ USD$/, ""));
		const rows = built
			.map(
				(seg) => `<tr class="mds-mb-row">
					<td class="mds-mb-dot-cell"><span class="mds-mb-dot" style="background:${seg.color}"></span></td>
					<td class="mds-mb-label-cell">${frappe.utils.escape_html(seg.label)}</td>
					<td class="mds-mb-amount-cell">${fmtAmt(seg.amount)}</td>
					<td class="mds-mb-pct-cell"><span class="mds-mb-badge" style="color:${seg.color};background:${seg.color}1a">${frappe.utils.escape_html(seg.pctDisp)}</span></td>
				</tr>`
			)
			.join("");
		const legend = `<table class="mds-mb-legend">
			<tbody>${rows}</tbody>
		</table>`;

		this.$marginBonus.html(`<div class="mds-mb-wrap">${svg}${legend}</div>`);
	}

	render_delta_badge(value, valueDisplay) {
		const numericValue = Number(value || 0);
		const isUp = numericValue >= 0;
		const cssClass = isUp ? "is-up" : "is-down";
		const trendIcon = isUp
			? `
				<svg class="mds-trend-arrow ${cssClass}" viewBox="0 0 20 20" fill="none" aria-hidden="true">
					<path d="M3 14L8 9L11 12L17 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>
					<path d="M12.5 6H17V10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>
				</svg>
			`
			: `
				<svg class="mds-trend-arrow ${cssClass}" viewBox="0 0 20 20" fill="none" aria-hidden="true">
					<path d="M3 6L8 11L11 8L17 14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>
					<path d="M12.5 14H17V9.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>
				</svg>
			`;
		return `
			<em class="${cssClass}">
				${trendIcon}
				${frappe.utils.escape_html(valueDisplay || "0.0%")}
			</em>
		`;
	}

	render_average_check() {
		const data = this.data?.average_check || {};
		this.$averageCheck.html(`
			<h2>СРЕДНИЙ ЧЕК</h2>
			<div class="mds-price-row">
				<div>
					<span>Цена продажи</span>
					<strong>${frappe.utils.escape_html(data.selling_price_display || "0 UZS")}</strong>
				</div>
				${this.render_delta_badge(data.selling_change, data.selling_change_display)}
			</div>
			<div class="mds-price-row">
				<div>
					<span>Себестоимость</span>
					<strong class="is-muted">${frappe.utils.escape_html(data.cost_price_display || "0 UZS")}</strong>
				</div>
				${this.render_delta_badge(data.cost_change, data.cost_change_display)}
			</div>
		`);
	}

	render_business_health() {
		const data = this.data?.average_check || {};
		const healthRatio = Number(data.health_ratio || 0);
		const healthRatioCapped = Math.max(0, Math.min(100, Number(data.health_ratio_capped || 0)));
		return `
			<div class="mds-health-card mds-health-card--embedded">
				<div class="mds-health-head">
					<div>
						<span>Состояние бизнеса</span>
						<strong>${frappe.utils.escape_html(data.health_ratio_display || "0.0%")}</strong>
					</div>
					<em class="${healthRatio <= 30 ? "is-good" : healthRatio <= 50 ? "is-warn" : "is-risk"}">
						Долг / Продажи
					</em>
				</div>
				<div class="mds-health-bar">
					<div class="mds-health-scale"></div>
					<div class="mds-health-pointer" style="left: ${healthRatioCapped}%;"></div>
				</div>
				<div class="mds-health-ticks">
					<span>0%</span>
					<span>30%</span>
					<span>50%</span>
					<span>100%</span>
				</div>
				<div class="mds-health-meta">
					<div>
						<span>Продажи</span>
						<strong>${frappe.utils.escape_html(data.health_sales_display || "0 USD")}</strong>
					</div>
					<div>
						<span>Долг</span>
						<strong>${frappe.utils.escape_html(data.health_debt_display || "0 USD")}</strong>
					</div>
				</div>
			</div>
		`;
	}

	render_business_health_card() {
		this.$businessHealth.html(`
			<h2>СОСТОЯНИЕ БИЗНЕСА</h2>
			${this.render_business_health()}
		`);
	}

	render_balance_details() {
		const data = this.data?.balance_details || {};
		const items = data.items || [];
		this.$balanceDetails.html(`
			<h2>ДЕТАЛИ БАЛАНСА</h2>
			${items
				.map((item) => this.render_balance_item(item.label, item.value))
				.join("")}
			<div class="mds-total-balance">
				<span>ОБЩИЙ БАЛАНС</span>
				<strong>${frappe.utils.escape_html(data.total_balance || "0 USD")}</strong>
			</div>
		`);
	}

	render_unit_cost() {
		const breakEven = this.data?.break_even || {};
		const planRatio = Math.max(0, Math.min(100, Number(breakEven.plan_ratio || 0)));
		const currentRatio = Math.max(planRatio, Math.min(100, Number(breakEven.current_ratio || 0)));
		const greenWidth = Math.max(currentRatio - planRatio, 0);
		this.$unitCost.html(`
			<h2>ТОЧКА БЕЗУБЫТОЧНОСТИ</h2>
			<div class="mds-progress-head">
				<span class="mds-progress-title">${frappe.utils.escape_html(breakEven.title || "Производственный прогресс")}</span>
				<strong class="mds-progress-summary">${frappe.utils.escape_html(breakEven.summary || "0t / 0t")}</strong>
			</div>
			<div class="mds-progress" style="--mds-plan-ratio:${planRatio}%; --mds-current-ratio:${currentRatio}%; --mds-green-width:${greenWidth}%;">
				<div class="mds-progress-line mds-progress-line--red"></div>
				<div class="mds-progress-line mds-progress-line--green"></div>
				<span class="mds-progress-dot mds-progress-dot--start"></span>
				<span class="mds-progress-dot mds-progress-dot--plan"></span>
				<span class="mds-progress-dot mds-progress-dot--current"></span>
			</div>
			<div class="mds-progress-scale">
				<span class="mds-progress-badge mds-progress-badge--start">${frappe.utils.escape_html(breakEven.start_label || "0t")}</span>
				<span class="mds-progress-badge mds-progress-badge--plan">${frappe.utils.escape_html(breakEven.plan_label || "План: 0t")}</span>
				<span class="mds-progress-badge mds-progress-badge--current">${frappe.utils.escape_html(breakEven.current_label || "Текущее: 0t")}</span>
			</div>
		`);
	}

	render_profit_chart() {
		const profitData = this.data?.net_profit_profitability?.series || [];
		const maxProfitValue = Math.max(100, ...profitData.map((row) => Math.max(0, Number(row.profit || 0))));
		const maxProfitabilityValue = Math.max(10, ...profitData.map((row) => Math.max(0, Number(row.profitability || 0))));
		const axisPadding = Math.max(maxProfitValue * 0.2, 10);
		const axisTop = Math.ceil((maxProfitValue + axisPadding) / 10) * 10;
		const axisValues = [axisTop, axisTop * (2 / 3), axisTop * (1 / 3), 0];
		const formatAxisValue = (value) => {
			if (!value) {
				return "0 K";
			}

			const absoluteAmount = value * 1000;
			if (Math.abs(absoluteAmount) >= 1000000) {
				const millions = absoluteAmount / 1000000;
				const roundedMillions = Math.abs(millions) >= 10 ? Math.round(millions) : Number(millions.toFixed(1));
				return `${roundedMillions} M`;
			}

			const roundedThousands = value >= 10 ? Math.round(value) : Number(value.toFixed(1));
			return `${roundedThousands} K`;
		};
		this.$profitChart.html(`
			<div class="mds-profit-plot">
				<div class="mds-profit-axis">
					${axisValues
						.map(
							(value) => `
								<div class="mds-profit-axis-row">
									<span class="mds-profit-axis-label">${formatAxisValue(value)}</span>
									<span class="mds-profit-axis-line"></span>
								</div>
							`
						)
						.join("")}
				</div>
				<div class="mds-profit-bars" style="grid-template-columns: repeat(${profitData.length || 1}, minmax(0, 1fr));">
					${profitData
						.map((row) => {
							const profitValue = Number(row.profit || 0);
							const profitabilityValue = Number(row.profitability || 0);
							const profitHeight = profitValue > 0 ? Math.max((profitValue / axisTop) * 100, 3) : 0;
							const profitabilityHeight = profitabilityValue > 0 ? Math.max((profitabilityValue / maxProfitabilityValue) * 100, 3) : 0;
							return `
								<div class="mds-profit-group">
									<div class="mds-profit-columns">
										<div class="mds-profit-bar-wrap">
											<span class="mds-profit-value mds-profit-value--blue">${frappe.utils.escape_html(row.profit_display || "0K")}</span>
											<div class="mds-profit-bar mds-profit-bar--blue ${profitHeight ? "" : "is-zero"}" style="height:${profitHeight}%; width: 10px;"></div>
										</div>
										<div class="mds-profit-bar-wrap">
											<span class="mds-profit-value mds-profit-value--green">${frappe.utils.escape_html(row.profitability_display || "0.0%")}</span>
											<div class="mds-profit-bar mds-profit-bar--green ${profitabilityHeight ? "" : "is-zero"}" style="height:${profitabilityHeight}%; width: 10px;"></div>
										</div>
									</div>
									<span class="mds-profit-month">${frappe.utils.escape_html(this.monthLabels[row.month] || row.month)}</span>
								</div>
							`;
						})
						.join("")}
				</div>
			</div>
		`);
	}
};
