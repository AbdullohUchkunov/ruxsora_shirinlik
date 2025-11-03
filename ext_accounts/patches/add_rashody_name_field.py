import frappe

def execute():
    """
    Add rashody_name field to all existing Rashody records
    """
    # Reload DocType with module name
    frappe.reload_doc("ruxsora_app", "doctype", "rashody")
    
    # Update all existing Rashody records
    rashody_records = frappe.get_all("Rashody", fields=["name", "account_name"])
    
    for rec in rashody_records:
        frappe.db.set_value("Rashody", rec.name, "rashody_name", rec.account_name, update_modified=False)
    
    frappe.db.commit()
    
    print(f"✅ Updated {len(rashody_records)} Rashody records with rashody_name field")
