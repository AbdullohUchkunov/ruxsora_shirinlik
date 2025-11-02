frappe.query_reports["Akt Sverka"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("Сана дан"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("Сана гача"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "party_type",
            "label": __("Контрагент тури"),
            "fieldtype": "Select",
            "options": "\nCustomer\nSupplier\nEmployee\nOther",
            "default": "Customer",
            "reqd": 1
        },
        {
            "fieldname": "party",
            "label": __("Контрагент"),
            "fieldtype": "Dynamic Link",
            "reqd": 1,
            "get_options": function() {
                var party_type = frappe.query_report.get_filter_value('party_type');
                var party = frappe.query_report.get_filter_value('party');
                if(party && !party_type) {
                    frappe.throw(__("Please select Party Type first"));
                }
                return party_type;
            }
        }
    ]
}
