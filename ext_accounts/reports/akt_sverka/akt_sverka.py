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
        {"label": "Ҳужжат тури", "fieldname": "voucher_type", "fieldtype": "Data", "width": 150},
        {"label": "Ҳужжат №", "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 120},
        {"label": "Маҳсулот номи", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Миқдори", "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": "Нархи", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
        {"label": "Сумма", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": "Валюта", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": "Кредит", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Дебет", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Қолдиқ", "fieldname": "balance", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    party_type = filters.get("party_type")
    party = filters.get("party")

    # Boshlang‘ich qoldiq (до from_date)
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
        "voucher_type": "Boshlang‘ich qoldiq",
        "voucher_no": "",
        "item_name": "",
        "qty": "",
        "rate": "",
        "amount": "",
        "currency": "UZS",
        "credit": 0,
        "debit": 0,
        "balance": opening_balance
    })

    # Asosiy harakatlar
    entries = frappe.db.sql("""
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

    for e in entries:
        balance += flt(e.debit) - flt(e.credit)
        data.append({
            "posting_date": e.posting_date,
            "voucher_type": e.voucher_type,
            "voucher_no": e.voucher_no,
            "item_name": "",
            "qty": "",
            "rate": "",
            "amount": e.debit or e.credit,
            "currency": e.currency,
            "credit": e.credit,
            "debit": e.debit,
            "balance": balance,
        })

    return data
