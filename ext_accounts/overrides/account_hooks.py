# ext_accounts/overrides/account_hooks.py
"""
Account DocType hooks to auto-create/update Rashody records
when accounts under 5200 are created/updated/deleted.
"""
import frappe
from frappe import _

from ext_accounts.ruxsora_app.doctype.kassa.kassa import is_under_indirect_expense_group


def after_insert(doc, method=None):
    """
    Account yaratilganda - agar 5200 child bo'lsa, Rashody record yaratish.
    """
    if should_create_rashody(doc):
        create_rashody_record(doc)


def on_update(doc, method=None):
    """
    Account yangilanganda - Rashody recordni ham yangilash.
    """
    if should_create_rashody(doc):
        # Agar Rashody yo'q bo'lsa, yaratish
        if not frappe.db.exists("Rashody", doc.name):
            create_rashody_record(doc)
        else:
            # Mavjud Rashody ni yangilash
            update_rashody_record(doc)
    else:
        # Agar parent_account o'zgargan va endi 5200 child emas bo'lsa, Rashody ni o'chirish
        if frappe.db.exists("Rashody", doc.name):
            frappe.delete_doc("Rashody", doc.name, force=True, ignore_permissions=True)


def on_trash(doc, method=None):
    """
    Account o'chirilganda - Rashody recordni ham o'chirish.
    """
    if frappe.db.exists("Rashody", doc.name):
        frappe.delete_doc("Rashody", doc.name, force=True, ignore_permissions=True)


def should_create_rashody(account_doc):
    """
    Check if Rashody record should be created for this account.
    
    Criteria (Kassa'dagi "Счет расходов" filtri bilan bir xil):
    - kompaniyaning Indirect Expenses (5200) guruhi ichida, istalgan chuqurlikda
    - is_group = 0 (ledger account)
    - root_type = "Expense"
    - disabled = 0
    """
    if account_doc.is_group or account_doc.root_type != "Expense" or account_doc.disabled:
        return False

    return is_under_indirect_expense_group(account_doc.parent_account, account_doc.company)


def create_rashody_record(account_doc):
    """Create Rashody record for the account."""
    try:
        rashody = frappe.get_doc({
            "doctype": "Rashody",
            "expense_account": account_doc.name,
            "account_name": account_doc.account_name,
            "company": account_doc.company
        })
        rashody.insert(ignore_permissions=True)
        
        frappe.msgprint(
            _("Rashody record created for account {0}").format(account_doc.name),
            alert=True,
            indicator="green"
        )
    except Exception as e:
        frappe.log_error(f"Failed to create Rashody for {account_doc.name}: {str(e)}")


def update_rashody_record(account_doc):
    """Update existing Rashody record."""
    try:
        rashody = frappe.get_doc("Rashody", account_doc.name)
        rashody.account_name = account_doc.account_name
        rashody.company = account_doc.company
        rashody.save(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Failed to update Rashody for {account_doc.name}: {str(e)}")
