import frappe

def execute():
    # Agar "Other" mavjud bo'lsa, account_type ni Payable qilib qo'yamiz
    if frappe.db.exists("Party Type", "Other"):
        frappe.db.set_value("Party Type", "Other", "account_type", "Payable")
        frappe.clear_cache(doctype="Party Type")
