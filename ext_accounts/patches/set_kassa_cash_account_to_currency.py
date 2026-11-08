import frappe


def execute():
    """Eski Kassa hujjatlarida "куда" kassa valyutasini to'ldirish (Остаток (куда) to'g'ri belgida chiqishi uchun)"""
    # patches.txt bo'limsiz - patch model sync'dan oldin ishlaydi, shuning uchun avval doctype'ni yuklaymiz
    frappe.reload_doc("ruxsora_app", "doctype", "kassa")

    frappe.db.sql(
        """
        UPDATE `tabKassa` k
        JOIN `tabAccount` a ON a.name = k.cash_account_to
        SET k.cash_account_to_currency = a.account_currency
        WHERE IFNULL(k.cash_account_to, '') != ''
          AND IFNULL(k.cash_account_to_currency, '') = ''
        """
    )
