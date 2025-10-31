import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    # 1) Custom Field: other_name (Data)
    meta = frappe.get_meta("Other", cached=False)
    if not meta.get_field("other_name"):
        create_custom_fields({
            "Other": [{
                "fieldname": "other_name",
                "label": "Other Name",
                "fieldtype": "Data",
                "insert_after": "party_name",
                "in_list_view": 1,
                "fetch_from": "party_name"  # party_name bilan avtomatik to'ldirsin
            }]
        }, update=True)

    # 2) Mavjud yozuvlar uchun backfill
    # (agar fetch_from ishlamasa ham bazada qiymat turadi)
    frappe.db.sql("""
        UPDATE `tabOther`
        SET other_name = party_name
        WHERE (other_name IS NULL OR other_name = '')
    """)
