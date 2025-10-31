import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    custom_fields = {
        "Payment Entry": [
            {
                "fieldname": "custom_other_party",
                "label": "Other Party",
                "fieldtype": "Link",
                "options": "Other",
                "depends_on": 'eval:doc.party_type=="Other"',
                "insert_after": "party"
            }
        ]
    }
    create_custom_fields(custom_fields, update=True)
