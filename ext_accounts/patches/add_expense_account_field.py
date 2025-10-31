import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    cf = frappe.get_meta("Payment Entry", cached=False).get_field("expense_account")
    if cf:  # allaqachon bor
        return
    create_custom_fields({
        "Payment Entry": [{
            "fieldname": "expense_account",
            "label": "Expense Account",
            "fieldtype": "Link",
            "options": "Account",
            "depends_on": 'eval:doc.party_type=="Расходы"',
            "insert_after": "party"
        }]
    }, update=True)