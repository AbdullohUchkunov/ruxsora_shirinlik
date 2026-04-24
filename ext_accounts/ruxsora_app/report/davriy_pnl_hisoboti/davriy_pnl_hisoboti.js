frappe.query_reports["Davriy PnL Hisoboti"] = {
	filters: [
		{
			fieldname: "report_date",
			label: __("Sana"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "currency",
			label: __("Valyuta"),
			fieldtype: "Link",
			options: "Currency",
			default: "USD",
			read_only: 1,
		},
		{
			fieldname: "company",
			label: __("Kompaniya"),
			fieldtype: "Link",
			options: "Company",
			default: "Ruxsora",
			read_only: 1,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		const isValueCol = column.fieldname !== "label";

		// ── Percentage rows ────────────────────────────────────────────────────
		if (data.is_pct_row && isValueCol) {
			// value is the raw float (e.g. 40.5) — skip default_formatter
			const num = (value !== null && value !== undefined)
				? parseFloat(value)
				: 0;
			const display = isNaN(num) ? "0.0 %" : num.toFixed(1) + " %";
			return `<span style="font-weight:700;color:#cf222e;">${display}</span>`;
		}

		value = default_formatter(value, row, column, data);

		// ── Profit / gross / net rows ──────────────────────────────────────────
		if (data.is_profit_row) {
			const borderStyle = data.is_separator
				? "border-top:2px solid #f5b8b8;display:block;padding-top:4px;"
				: "";
			return `<span style="font-weight:700;color:#cf222e;${borderStyle}">${value}</span>`;
		}

		// ── Section header rows (indent 0, bold, not profit) ──────────────────
		if (data.indent === 0 && data.bold) {
			return `<span style="font-weight:700;">${value}</span>`;
		}

		// ── Separator rows (empty label rows) ─────────────────────────────────
		if (data.is_separator) {
			return `<span style="border-top:2px solid #ddd;display:block;">${value}</span>`;
		}

		return value;
	},
};
