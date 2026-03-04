# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, fmt_money
from ext_accounts.telegram_bot import send_message, get_chat_id_for_party


def get_party_gl_balance(party_type, party, company):
    """
    Party ning GL balansini valyuta bo'yicha hisoblash.
    Natija: {currency: balance} dict.
    Customer uchun: musbat = bizga qarzdor.
    Supplier/Employee uchun: musbat = biz qarzdormiz.
    """
    try:
        rows = frappe.db.sql("""
            SELECT
                account_currency AS currency,
                SUM(debit_in_account_currency) - SUM(credit_in_account_currency) AS balance
            FROM `tabGL Entry`
            WHERE party_type = %s
              AND party = %s
              AND company = %s
              AND is_cancelled = 0
            GROUP BY account_currency
        """, (party_type, party, company), as_dict=True)

        result = {}
        for row in rows:
            if row.balance is None:
                continue
            balance = flt(row.balance)
            if party_type == "Customer":
                result[row.currency] = -balance
            else:
                result[row.currency] = balance
        return result
    except Exception as e:
        frappe.log_error(f"GL balans xatosi: {str(e)}", "Telegram Notifications")
        return {}


DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


def format_currency_amount(amount, currency):
    """Summa + valyuta formatlash"""
    abs_amount = abs(flt(amount))
    if currency == "USD":
        return f"{abs_amount:,.2f} $"
    elif currency == "UZS":
        return f"{abs_amount:,.0f} so'm"
    else:
        return f"{abs_amount:,.2f} {currency}"


def format_balance_line(balances, party_type):
    """
    Qarzdorlik satrini formatlash.
    balances: {currency: balance} dict
    """
    if not balances or all(flt(v) == 0 for v in balances.values()):
        return "✅ Hisob-kitob yo'q"

    lines = []
    for currency, balance in balances.items():
        b = flt(balance)
        if b == 0:
            continue
        amount_str = format_currency_amount(b, currency)
        if b > 0:
            if party_type == "Customer":
                lines.append(f"📌 Sizning qarzingiz: <b>{amount_str}</b>")
            else:
                lines.append(f"📌 Bizning qarzimiz: <b>{amount_str}</b>")
        else:
            if party_type == "Customer":
                lines.append(f"📌 Bizning qarzimiz: <b>{amount_str}</b>")
            else:
                lines.append(f"📌 Sizning qarzingiz: <b>{amount_str}</b>")

    return "\n".join(lines) if lines else "✅ Hisob-kitob yo'q"


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
    items_lines = []
    for i, item in enumerate(doc.items, 1):
        qty = flt(item.qty)
        rate = flt(item.valuation_rate or item.rate)
        amount = flt(item.amount)
        items_lines.append(
            f"{i}. <b>{item.item_name}</b>\n"
            f"   {qty:g} dona × {format_currency_amount(rate, currency)}"
            f" = <b>{format_currency_amount(amount, currency)}</b>"
        )
    items_text = "\n".join(items_lines)

    total = format_currency_amount(flt(doc.grand_total), currency)
    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, party_type)

    message = (
        f"📦 <b>Sizdan mahsulot qabul qilindi</b>\n"
        f"{DIVIDER}\n"
        f"🏢 {doc.company}\n"
        f"📄 {doc.name}\n"
        f"📅 {doc.posting_date}\n"
        f"{DIVIDER}\n"
        f"{items_text}\n"
        f"{DIVIDER}\n"
        f"💵 Jami: <b>{total}</b>\n"
        f"{DIVIDER}\n"
        f"{balance_text}"
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
    items_lines = []
    for i, item in enumerate(doc.items, 1):
        qty = flt(item.qty)
        rate = flt(item.rate)
        amount = flt(item.amount)
        items_lines.append(
            f"{i}. <b>{item.item_name}</b>\n"
            f"   {qty:g} dona × {format_currency_amount(rate, currency)}"
            f" = <b>{format_currency_amount(amount, currency)}</b>"
        )
    items_text = "\n".join(items_lines)

    total = format_currency_amount(flt(doc.grand_total), currency)
    balance = get_party_gl_balance(party_type, party, company)
    balance_text = format_balance_line(balance, party_type)

    message = (
        f"🛒 <b>Sizga mahsulot sotildi</b>\n"
        f"{DIVIDER}\n"
        f"🏢 {doc.company}\n"
        f"📄 {doc.name}\n"
        f"📅 {doc.posting_date}\n"
        f"{DIVIDER}\n"
        f"{items_text}\n"
        f"{DIVIDER}\n"
        f"💵 Jami: <b>{total}</b>\n"
        f"{DIVIDER}\n"
        f"{balance_text}"
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
    balance_text = format_balance_line(balance, party_type)

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
            action = "Sizga to'lov amalga oshirildi"
        else:
            emoji = "💰"
            action = "Sizdan to'lov qabul qilindi"
    else:  # Customer
        if doc.payment_type == "Receive":
            emoji = "💰"
            action = "Sizdan to'lov qabul qilindi"
        else:
            emoji = "💸"
            action = "Sizga pul qaytarildi"

    message = (
        f"{emoji} <b>{action}</b>\n"
        f"{DIVIDER}\n"
        f"🏢 {doc.company}\n"
        f"📄 {doc.name}\n"
        f"📅 {doc.posting_date}\n"
        f"{DIVIDER}\n"
        f"💵 To'lov miqdori: <b>{amount_text}</b>\n"
        f"{DIVIDER}\n"
        f"{balance_text}"
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
    balance_text = format_balance_line(balance, party_type)

    message = (
        f"📋 <b>Oylik maosh hisoblandi</b>\n"
        f"{DIVIDER}\n"
        f"🏢 {doc.company}\n"
        f"📄 {doc.name}\n"
        f"📅 {doc.start_date} — {doc.end_date}\n"
        f"{DIVIDER}\n"
        f"💵 Oylik miqdori: <b>{amount_text}</b>\n"
        f"{DIVIDER}\n"
        f"{balance_text}"
    )

    send_message(chat_id, message)
