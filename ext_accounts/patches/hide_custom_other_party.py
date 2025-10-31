import frappe

def execute():
    cf_name = frappe.db.get_value(
        "Custom Field",
        {"dt": "Payment Entry", "fieldname": "custom_other_party"},
        "name"
    )
    if cf_name:
        frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
        frappe.clear_cache(doctype="Payment Entry")
