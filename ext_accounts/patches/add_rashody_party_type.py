import frappe

def execute():
    # Check both Rashody and Расходы
    if frappe.db.exists("Party Type", "Rashody"):
        print("✅ Party Type 'Rashody' already exists")
        return
    
    if frappe.db.exists("Party Type", "Расходы"):
        # Rename Расходы to Rashody
        frappe.db.sql("UPDATE `tabParty Type` SET name='Rashody' WHERE name='Расходы'")
        frappe.db.commit()
        print("✅ Party Type renamed from 'Расходы' to 'Rashody'")
        return

    # Create new Party Type
    doc = frappe.get_doc({
        "doctype": "Party Type",
        "party_type": "Rashody",
        "account_type": "Payable",
    })
    # muammoli link tekshiruvini chetlab o'tamiz
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("✅ Party Type 'Rashody' created successfully")
