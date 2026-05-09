import frappe

rows = frappe.db.sql("""
    SELECT 
        TRIM(COALESCE(sii.item_name, '')) AS item_name,
        TRIM(COALESCE(sii.item_code, '')) AS item_code,
        si.is_return,
        COUNT(*) AS cnt,
        SUM(ABS(COALESCE(sii.base_net_amount, sii.base_amount, sii.net_amount, sii.amount, 0))) AS total_amount
    FROM `tabSales Invoice` si
    INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
    WHERE si.docstatus = 1
      AND (
          LOWER(TRIM(COALESCE(sii.item_name, ''))) LIKE '%%бонус%%'
          OR LOWER(TRIM(COALESCE(sii.item_code, ''))) LIKE '%%бонус%%'
          OR LOWER(TRIM(COALESCE(sii.item_name, ''))) LIKE '%%скидка%%'
          OR LOWER(TRIM(COALESCE(sii.item_code, ''))) LIKE '%%скидка%%'
          OR LOWER(TRIM(COALESCE(sii.item_name, ''))) LIKE '%%дилл%%'
          OR LOWER(TRIM(COALESCE(sii.item_code, ''))) LIKE '%%дилл%%'
      )
    GROUP BY TRIM(COALESCE(sii.item_name, '')), TRIM(COALESCE(sii.item_code, '')), si.is_return
    ORDER BY si.is_return, item_name
""", as_dict=True)

for row in rows:
    print(f"item_name='{row.item_name}', item_code='{row.item_code}', is_return={row.is_return}, cnt={row.cnt}, total={row.total_amount}")

if not rows:
    print("No matching items found!")
    # Check if there are ANY return invoices
    ret_count = frappe.db.sql("SELECT COUNT(*) as c FROM `tabSales Invoice` WHERE docstatus=1 AND COALESCE(is_return,0)=1")[0][0]
    print(f"Total return invoices: {ret_count}")
    
    # Check all distinct item names in returns
    ret_items = frappe.db.sql("""
        SELECT DISTINCT TRIM(COALESCE(sii.item_name, '')) AS item_name, TRIM(COALESCE(sii.item_code, '')) AS item_code
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1 AND COALESCE(si.is_return, 0) = 1
        LIMIT 30
    """, as_dict=True)
    print("Items in return invoices:")
    for item in ret_items:
        print(f"  name='{item.item_name}', code='{item.item_code}'")
