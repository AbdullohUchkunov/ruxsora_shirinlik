import frappe

def execute():
    if frappe.db.exists("Party Type", "Other"):
        return
    doc = frappe.get_doc({
        "doctype": "Party Type",
        "party_type": "Other",
        "account_type": "Receivable"  # kerak bo‘lsa "Payable"
    })
    doc.insert()