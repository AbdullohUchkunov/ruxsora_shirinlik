import frappe

def execute():
    if frappe.db.exists("Party Type", "Расходы"):
        return

    doc = frappe.get_doc({
        "doctype": "Party Type",
        "party_type": "Расходы",
        "account_type": "Payable",
    })
    # muammoli link tekshiruvini chetlab o'tamiz
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
