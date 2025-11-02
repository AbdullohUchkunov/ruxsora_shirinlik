import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Сана", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Ҳужжат", "fieldname": "voucher_type", "fieldtype": "Data", "width": 150},
        {"label": "Ҳужжат №", "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 120},
        {"label": "Маҳсулот номи", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Миқдори", "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": "Нархи", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
        {"label": "Валюта", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": "Кредит", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Дебет", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Қолдиқ", "fieldname": "balance", "fieldtype": "Currency", "width": 120},
    ]


def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    party_type = filters.get("party_type")
    party = filters.get("party")

    # Boshlang'ich qoldiq (до from_date)
    opening_balance = frappe.db.sql("""
        SELECT 
            IFNULL(SUM(debit - credit), 0)
        FROM `tabGL Entry`
        WHERE posting_date < %s
          AND party_type = %s
          AND party = %s
    """, (from_date, party_type, party))[0][0]

    data = []

    # Opening qoldiq birinchi qator
    data.append({
        "posting_date": from_date,
        "voucher_type": "Boshlang'ich qoldiq",
        "voucher_no": "",
        "item_name": "",
        "qty": None,
        "rate": None,
        "currency": "UZS",
        "credit": 0,
        "debit": 0,
        "balance": opening_balance
    })

    # GL Entry'larni olish
    gl_entries = frappe.db.sql("""
        SELECT 
            posting_date, voucher_type, voucher_no,
            debit, credit, account_currency AS currency
        FROM `tabGL Entry`
        WHERE posting_date BETWEEN %s AND %s
          AND party_type = %s
          AND party = %s
        ORDER BY posting_date ASC, creation ASC
    """, (from_date, to_date, party_type, party), as_dict=True)

    balance = opening_balance

    # Har bir GL Entry uchun detail ma'lumotlarni olish
    for gl in gl_entries:
        voucher_type = gl.voucher_type
        voucher_no = gl.voucher_no
        
        # Purchase Invoice uchun item details
        if voucher_type == "Purchase Invoice":
            items = get_purchase_invoice_items(voucher_no)
            if items:
                # Har bir item uchun qator, lekin balance faqat oxirida
                total_credit = sum(flt(item.get('credit', 0)) for item in items)
                
                for idx, item in enumerate(items):
                    is_last_item = (idx == len(items) - 1)
                    if is_last_item:
                        balance -= total_credit  # Purchase Invoice da credit qarz oshadi (balance kamayadi)
                    
                    data.append({
                        "posting_date": gl.posting_date,
                        "voucher_type": voucher_type,
                        "voucher_no": voucher_no,
                        "item_name": item.get('item_name', ''),
                        "qty": item.get('qty'),
                        "rate": item.get('rate'),
                        "currency": item.get('currency', gl.currency),
                        "credit": item.get('credit', 0),
                        "debit": 0,
                        "balance": balance if is_last_item else None,
                    })
            else:
                # Agar item topilmasa, faqat GL entry ko'rsatish
                balance -= flt(gl.credit)
                data.append({
                    "posting_date": gl.posting_date,
                    "voucher_type": voucher_type,
                    "voucher_no": voucher_no,
                    "item_name": "",
                    "qty": None,
                    "rate": None,
                    "currency": gl.currency,
                    "credit": gl.credit,
                    "debit": 0,
                    "balance": balance,
                })
        
        # Sales Invoice uchun item details
        elif voucher_type == "Sales Invoice":
            items = get_sales_invoice_items(voucher_no)
            if items:
                # Har bir item uchun qator, lekin balance faqat oxirida
                total_debit = sum(flt(item.get('debit', 0)) for item in items)
                
                for idx, item in enumerate(items):
                    is_last_item = (idx == len(items) - 1)
                    if is_last_item:
                        balance += total_debit  # Sales Invoice da debit qarz kamayadi (balance oshadi)
                    
                    data.append({
                        "posting_date": gl.posting_date,
                        "voucher_type": voucher_type,
                        "voucher_no": voucher_no,
                        "item_name": item.get('item_name', ''),
                        "qty": item.get('qty'),
                        "rate": item.get('rate'),
                        "currency": item.get('currency', gl.currency),
                        "credit": 0,
                        "debit": item.get('debit', 0),
                        "balance": balance if is_last_item else None,
                    })
            else:
                balance += flt(gl.debit)
                data.append({
                    "posting_date": gl.posting_date,
                    "voucher_type": voucher_type,
                    "voucher_no": voucher_no,
                    "item_name": "",
                    "qty": None,
                    "rate": None,
                    "currency": gl.currency,
                    "credit": 0,
                    "debit": gl.debit,
                    "balance": balance,
                })
        
        # Payment Entry uchun
        elif voucher_type == "Payment Entry":
            payment_info = get_payment_entry_info(voucher_no)
            
            # Payment Entry da balance to'g'ri hisoblansin
            # Receive bo'lsa - credit (qarz kamayadi, balance oshadi)
            # Pay bo'lsa - debit (to'lov qildik, balance kamayadi)
            balance += flt(gl.debit) - flt(gl.credit)
            
            data.append({
                "posting_date": gl.posting_date,
                "voucher_type": voucher_type,
                "voucher_no": voucher_no,
                "item_name": payment_info.get('description', ''),
                "qty": None,
                "rate": payment_info.get('account', ''),
                "currency": gl.currency,
                "credit": gl.credit,
                "debit": gl.debit,
                "balance": balance,
            })
        
        # Journal Entry uchun
        elif voucher_type == "Journal Entry":
            je_accounts = get_journal_entry_accounts(voucher_no, party_type, party)
            if je_accounts:
                # Har bir accounting entry uchun qator, balance faqat oxirida
                total_debit = sum(flt(acc.get('debit', 0)) for acc in je_accounts)
                total_credit = sum(flt(acc.get('credit', 0)) for acc in je_accounts)
                
                for idx, acc in enumerate(je_accounts):
                    is_last_item = (idx == len(je_accounts) - 1)
                    if is_last_item:
                        balance += total_debit - total_credit
                    
                    data.append({
                        "posting_date": gl.posting_date,
                        "voucher_type": voucher_type,
                        "voucher_no": voucher_no,
                        "item_name": acc.get('account', ''),
                        "qty": None,
                        "rate": None,
                        "currency": gl.currency,
                        "credit": acc.get('credit', 0),
                        "debit": acc.get('debit', 0),
                        "balance": balance if is_last_item else None,
                    })
            else:
                balance += flt(gl.debit) - flt(gl.credit)
                data.append({
                    "posting_date": gl.posting_date,
                    "voucher_type": voucher_type,
                    "voucher_no": voucher_no,
                    "item_name": "",
                    "qty": None,
                    "rate": None,
                    "currency": gl.currency,
                    "credit": gl.credit,
                    "debit": gl.debit,
                    "balance": balance,
                })
        
        # Boshqa document type'lar uchun
        else:
            balance += flt(gl.debit) - flt(gl.credit)
            data.append({
                "posting_date": gl.posting_date,
                "voucher_type": voucher_type,
                "voucher_no": voucher_no,
                "item_name": "",
                "qty": None,
                "rate": None,
                "currency": gl.currency,
                "credit": gl.credit,
                "debit": gl.debit,
                "balance": balance,
            })

    # Total qatorini qo'shish
    if len(data) > 1:  # Agar faqat opening balance dan ko'proq qator bo'lsa
        # Opening balance qatorini hisobga olmasdan total hisoblash
        total_credit = sum(flt(row.get('credit', 0)) for row in data if row.get('voucher_type') != 'Boshlang\'ich qoldiq')
        total_debit = sum(flt(row.get('debit', 0)) for row in data if row.get('voucher_type') != 'Boshlang\'ich qoldiq')
        
        data.append({
            "posting_date": to_date,
            "voucher_type": "Total",
            "voucher_no": "",
            "item_name": "",
            "qty": None,
            "rate": None,
            "currency": "",
            "credit": total_credit,
            "debit": total_debit,
            "balance": balance,  # Oxirgi balance
        })

    return data


def get_purchase_invoice_items(voucher_no):
    """Purchase Invoice item'larini olish"""
    items = frappe.db.sql("""
        SELECT 
            pii.item_name,
            pii.qty,
            pii.rate,
            pi.currency,
            pii.amount as credit,
            0 as debit
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pii.parent = %s
        ORDER BY pii.idx
    """, voucher_no, as_dict=True)
    
    return items


def get_sales_invoice_items(voucher_no):
    """Sales Invoice item'larini olish"""
    items = frappe.db.sql("""
        SELECT 
            sii.item_name,
            sii.qty,
            sii.rate,
            si.currency,
            0 as credit,
            sii.amount as debit
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.parent = %s
        ORDER BY sii.idx
    """, voucher_no, as_dict=True)
    
    return items


def get_payment_entry_info(voucher_no):
    """Payment Entry ma'lumotlarini olish"""
    payment = frappe.db.sql("""
        SELECT 
            payment_type,
            paid_from,
            paid_to
        FROM `tabPayment Entry`
        WHERE name = %s
    """, voucher_no, as_dict=True)
    
    if payment:
        p = payment[0]
        # Payment type ga qarab description va account
        if p.payment_type == 'Pay':
            return {
                'description': 'Pay',
                'account': p.paid_from
            }
        elif p.payment_type == 'Receive':
            return {
                'description': 'Receive',
                'account': p.paid_to
            }
        else:
            return {
                'description': p.payment_type,
                'account': p.paid_from or p.paid_to
            }
    
    return {'description': '', 'account': ''}


def get_journal_entry_accounts(voucher_no, party_type, party):
    """Journal Entry account'larini olish"""
    accounts = frappe.db.sql("""
        SELECT 
            account,
            debit,
            credit
        FROM `tabJournal Entry Account`
        WHERE parent = %s
          AND party_type = %s
          AND party = %s
        ORDER BY idx
    """, (voucher_no, party_type, party), as_dict=True)
    
    return accounts
