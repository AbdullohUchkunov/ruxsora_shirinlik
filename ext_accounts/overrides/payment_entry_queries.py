# ext_accounts/overrides/payment_entry_queries.py
import frappe

@frappe.whitelist()
def get_party_type(doctype, txt, searchfield, start, page_len, filters):
    # Faqat standart turlar (Расходы YO'Q)
    allowed = ["Customer", "Supplier", "Employee", "Shareholder", "Other"]

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
        SELECT name as value, name as label
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
                ELSE 6
            END, name
        LIMIT %s OFFSET %s
    """
    res = frappe.db.sql(query, params, as_dict=1)
    return [[d.value, d.label] for d in res]
