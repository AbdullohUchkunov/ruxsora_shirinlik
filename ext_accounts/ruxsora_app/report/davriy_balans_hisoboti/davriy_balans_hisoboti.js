frappe.query_reports["Davriy Balans Hisoboti"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Dan"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Gacha"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "party_type",
			label: __("Kontragent turi"),
			fieldtype: "Select",
			options: "Customer\nSupplier\nEmployee",
			reqd: 1,
			on_change: function () {
				frappe.query_report.set_filter_value("party", "");
			},
		},
		{
			fieldname: "party",
			label: __("Kontragent"),
			fieldtype: "Dynamic Link",
			get_options: function () {
				return frappe.query_report.get_filter_value("party_type");
			},
		},
		{
			fieldname: "period",
			label: __("Davr turi"),
			fieldtype: "Select",
			options: "Monthly\nWeekly",
			default: "Monthly",
			reqd: 1,
		},
		{
			fieldname: "currency",
			label: __("Valyuta"),
			fieldtype: "Link",
			options: "Currency",
			default: "UZS",
		},
	],
};
