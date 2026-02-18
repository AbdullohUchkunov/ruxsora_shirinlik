# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, fmt_money
from ext_accounts.telegram_bot import send_message, get_chat_id_for_party


def get_party_gl_balance(party_type, party, company):
    """
    Party ning GL balansini hisoblash.
    Natija: + bo'lsa biz qarzdormiz, - bo'lsa u bizga qarzdor.

    Supplier uchun: credit - debit (payable account bo'yicha)
    Customer uchun: debit - credit (receivable account bo'yicha)
    Employee uchun: credit - debit (payable account bo'yicha)
    """
    try:
        result = frappe.db.sql("""
            SELECT
                SUM(debit) - SUM(credit) AS balance
            FROM `tabGL Entry`
            WHERE party_type = %s
              AND party = %s
              AND company = %s
              AND is_cancelled = 0
        """, (party_type, party, company), as_dict=True)

        if result and result[0].balance is not None:
            balance = flt(result[0].balance)
            # Customer: debit-credit musbat = bizga qarzdor, manfiy = biz qarzdormiz
            # Supplier/Employee: debit-credit musbat = biz qarzdormiz (ular bizga tovar bergan)
            if party_type == "Customer":
                # Receivable: debit > credit = bizga qarzdor → manfiy ko'rsatamiz
                return -balance
            else:
                # Payable: credit > debit = biz qarzdormiz → musbat ko'rsatamiz
                return balance
        return 0.0
    except Exception as e:
        frappe.log_error(f"GL balans xatosi: {str(e)}", "Telegram Notifications")
        return 0.0


def format_currency_amount(amount, currency):
    """Summa + valyuta formatlash"""
    abs_amount = abs(flt(amount))
    if currency == "USD":
        return f"{abs_amount:,.2f} USD"
    elif currency == "UZS":
        return f"{abs_amount:,.0f} UZS"
    else:
        return f"{abs_amount:,.2f} {currency}"


def format_balance_line(balance, currency):
    """Qarzdorlik satrini formatlash"""
    if flt(balance) == 0:
        return "0"
    elif flt(balance) > 0:
        return f"+{format_currency_amount(balance, currency)}"
    else:
        return f"-{format_currency_amount(balance, currency)}"


def send_notification(party_type, party, company, message):
    """Party ga Telegram xabar yuborish"""
    chat_id = get_chat_id_for_party(party_type, party)
    if not chat_id:
        return  # Ro'yxatdan o'tmagan yoki chat_id yo'q
    send_message(chat_id, message)


# ─── Purchase Invoice ─────────────────────────────────────────────────────────

def notify_purchase_invoice(doc, method=None):
    """Purchase Invoice submit → Supplier ga xabar"""
    if doc.docstatus != 1:
        return

    party_type = "Supplier"
    party = doc.supplier
    company = doc.company
    currency = doc.currency or "UZS"

    chat_id = get_chat_id_for_party(party_type, party)
    if not chat_id:
        return

    # Itemlar ro'yxati
    items_text = ""
    for item in doc.items:
        qty = flt(item.qty)
        rate = flt(item.valuation_rate or item.rate)
        amount = flt(item.amount)
        items_text += (
            f"\n• {item.item_name} — "
            f"{qty:g} dona × {format_currency_amount(rate, currency)} = "
            f"{format_currency_amount(amount, currency)}"
        )

    total = format_currency_amount(flt(doc.grand_total), currency)
    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, currency)

    message = (
        f"📦 <b>Sizdan mahsulot qabul qilindi</b>\n"
        f"📄 {doc.name}\n"
        f"{items_text}\n\n"
        f"<b>Jami:</b> {total}\n\n"
        f"💰 <b>Joriy hisobingiz:</b> {balance_text}"
    )

    send_message(chat_id, message)


# ─── Sales Invoice ────────────────────────────────────────────────────────────

def notify_sales_invoice(doc, method=None):
    """Sales Invoice submit → Customer ga xabar"""
    if doc.docstatus != 1:
        return

    party_type = "Customer"
    party = doc.customer
    company = doc.company
    currency = doc.currency or "UZS"

    chat_id = get_chat_id_for_party(party_type, party)
    if not chat_id:
        return

    # Itemlar ro'yxati
    items_text = ""
    for item in doc.items:
        qty = flt(item.qty)
        rate = flt(item.rate)
        amount = flt(item.amount)
        items_text += (
            f"\n• {item.item_name} — "
            f"{qty:g} dona × {format_currency_amount(rate, currency)} = "
            f"{format_currency_amount(amount, currency)}"
        )

    total = format_currency_amount(flt(doc.grand_total), currency)
    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, currency)

    message = (
        f"🛒 <b>Sizga mahsulot sotildi</b>\n"
        f"📄 {doc.name}\n"
        f"{items_text}\n\n"
        f"<b>Jami:</b> {total}\n\n"
        f"💰 <b>Joriy hisobingiz:</b> {balance_text}"
    )

    send_message(chat_id, message)


# ─── Payment Entry ────────────────────────────────────────────────────────────

def notify_payment_entry(doc, method=None):
    """Payment Entry submit → Party ga xabar"""
    if doc.docstatus != 1:
        return

    party_type = doc.party_type
    party = doc.party
    company = doc.company

    # Faqat Customer, Supplier, Employee uchun
    if party_type not in ("Customer", "Supplier", "Employee"):
        return

    chat_id = get_chat_id_for_party(party_type, party)
    if not chat_id:
        return

    # Miqdor va valyutani aniqlash
    if doc.payment_type == "Pay":
        amount = flt(doc.paid_amount)
        currency = doc.paid_from_account_currency or "UZS"
    else:
        amount = flt(doc.received_amount)
        currency = doc.paid_to_account_currency or "UZS"

    amount_text = format_currency_amount(amount, currency)
    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, currency)

    # Xabar matni: payment_type va party_type ga qarab
    if party_type == "Employee":
        if doc.payment_type == "Pay":
            emoji = "💵"
            action = "Sizga oylik to'landi"
        else:
            emoji = "💰"
            action = "Sizdan to'lov qabul qilindi"
    elif party_type == "Supplier":
        if doc.payment_type == "Pay":
            emoji = "💸"
            action = "Sizga pul berildi"
        else:
            emoji = "💰"
            action = "Sizdan pul qabul qilindi"
    else:  # Customer
        if doc.payment_type == "Receive":
            emoji = "💰"
            action = "Sizdan pul qabul qilindi"
        else:
            emoji = "💸"
            action = "Sizga pul berildi"

    message = (
        f"{emoji} <b>{action}</b>\n"
        f"📄 {doc.name}\n"
        f"<b>Miqdor:</b> {amount_text}\n\n"
        f"💰 <b>Joriy hisobingiz:</b> {balance_text}"
    )

    send_message(chat_id, message)


# ─── Salary Slip ──────────────────────────────────────────────────────────────

def notify_salary_slip(doc, method=None):
    """Salary Slip submit → Employee ga xabar"""
    if doc.docstatus != 1:
        return

    party_type = "Employee"
    party = doc.employee
    company = doc.company

    chat_id = get_chat_id_for_party(party_type, party)
    if not chat_id:
        return

    net_pay = flt(doc.net_pay)
    currency = frappe.get_cached_value("Company", company, "default_currency") or "UZS"
    amount_text = format_currency_amount(net_pay, currency)

    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, currency)

    message = (
        f"📋 <b>Siz oylik hisoblandi</b>\n"
        f"📄 {doc.name}\n"
        f"📅 {doc.start_date} — {doc.end_date}\n"
        f"<b>Oylik miqdori:</b> {amount_text}\n\n"
        f"💰 <b>Joriy hisobingiz:</b> {balance_text}"
    )

    send_message(chat_id, message)
