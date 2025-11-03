# ext_accounts/overrides/payment_entry_queries.py
import frappe

@frappe.whitelist()
def get_party_type(doctype, txt, searchfield, start, page_len, filters):
    """
    Payment Entry uchun Party Type query.
    Pay va Receive da Rashody ko'rinadi.
    """
    # Barcha ruxsat etilgan turlar (Rashody ham kiradi)
    allowed = ["Customer", "Supplier", "Employee", "Shareholder", "Other", "Rashody"]

    txt = txt or ""
    params = []

    search_conditions = ""
    if txt:
        search_conditions = " AND name LIKE %s"
        params.append(f"%{txt}%")

    in_clause = ", ".join(["%s"] * len(allowed))
    params = allowed + params
    params.extend([page_len, start])

    query = f"""
        SELECT 
            name as value, 
            CASE 
                WHEN name = 'Rashody' THEN 'Расходы'
                ELSE name 
            END as label
        FROM `tabParty Type`
        WHERE name IN ({in_clause})
        {search_conditions}
        ORDER BY
            CASE
                WHEN name='Customer' THEN 1
                WHEN name='Supplier' THEN 2
                WHEN name='Employee' THEN 3
                WHEN name='Shareholder' THEN 4
                WHEN name='Other' THEN 5
                WHEN name='Rashody' THEN 6
                ELSE 7
            END, name
        LIMIT %s OFFSET %s
    """
    res = frappe.db.sql(query, params, as_dict=1)
    return [[d.value, d.label] for d in res]


@frappe.whitelist()
def get_party_for_rashody(doctype, txt, searchfield, start, page_len, filters):
    """
    Party Type = Rashody bo'lganda, Party fieldida Rashody recordlarni qaytaradi.
    Barcha 5200 child accounts (limitni 999 ga oshiramiz).
    """
    company = filters.get("company") if filters else None
    if not company:
        # Default company
        company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    
    txt = txt or ""
    
    # Rashody DocType dan barcha recordlarni olish
    # page_len ni 999 ga oshiramiz (barcha recordlarni ko'rsatish uchun)
    max_results = 999
    
    query = """
        SELECT 
            expense_account as value,
            CONCAT(expense_account, ' - ', account_name) as description
        FROM `tabRashody`
        WHERE company = %s
        AND (expense_account LIKE %s OR account_name LIKE %s)
        ORDER BY expense_account
        LIMIT %s OFFSET %s
    """
    
    params = [company, f"%{txt}%", f"%{txt}%", max_results, start]
    res = frappe.db.sql(query, params, as_dict=1)
    
    # Return format: [[value, description], ...]
    return [[d.value, d.description] for d in res]
