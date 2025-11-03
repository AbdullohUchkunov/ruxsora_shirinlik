import frappe

def execute():
    """Create Rashody records for all child accounts under 5200 - Indirect Expenses"""
    
    # Get all non-group child accounts under 5200
    accounts = frappe.get_all(
        "Account",
        filters={
            "parent_account": "5200 - Indirect Expenses - R",
            "is_group": 0,
            "disabled": 0,
            "company": "Ruxsora"
        },
        fields=["name", "account_name", "company"]
    )
    
    created = 0
    skipped = 0
    
    for acc in accounts:
        # Check if Rashody record already exists
        if frappe.db.exists("Rashody", acc.name):
            skipped += 1
            continue
        
        # Create new Rashody record
        doc = frappe.get_doc({
            "doctype": "Rashody",
            "expense_account": acc.name,
            "account_name": acc.account_name,
            "company": acc.company
        })
        doc.insert(ignore_permissions=True)
        created += 1
    
    frappe.db.commit()
    
    print(f"✅ Created {created} Rashody records, Skipped {skipped} existing records")
    print(f"📊 Total Rashody records: {len(accounts)}")
