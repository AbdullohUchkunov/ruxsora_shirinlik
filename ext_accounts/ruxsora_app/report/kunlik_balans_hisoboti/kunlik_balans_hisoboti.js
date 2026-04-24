frappe.query_reports["Kunlik Balans Hisoboti"] = {
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

		value = default_formatter(value, row, column, data);

		if (data.is_total) {
			return `<span style="font-weight:700;border-top:2px solid #ddd;display:block;padding-top:4px;">${value}</span>`;
		}

		if (data.indent === 0 && data.bold) {
			return `<span style="font-weight:700;">${value}</span>`;
		}

		if (data.bold) {
			return `<span style="font-weight:600;">${value}</span>`;
		}

		return value;
	},
};
