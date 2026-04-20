# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import json
import requests
import frappe
from frappe import _
from frappe.utils import today, add_days, add_months, getdate, flt


# ─── Asosiy yordamchi funksiyalar ────────────────────────────────────────────

def get_bot_token():
    from frappe.utils.password import get_decrypted_password
    try:
        name = frappe.db.get_value("Telegram Settings", {}, "name")
        if not name:
            return None
        return get_decrypted_password("Telegram Settings", name, "telegram_token")
    except Exception:
        return frappe.db.get_value("Telegram Settings", name, "telegram_token")


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    token = get_bot_token()
    if not token:
        frappe.log_error("Telegram bot token kiritilmagan", "Telegram Bot")
        return False
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload, timeout=10
        )
        if not r.ok:
            frappe.log_error(r.text, f"Telegram sendMessage Error (chat_id={chat_id})")
        return r.ok
    except Exception as e:
        frappe.log_error(str(e), "Telegram Bot")
        return False


def send_document(chat_id, file_bytes, filename, caption=""):
    token = get_bot_token()
    if not token:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, file_bytes, "application/pdf")},
            timeout=60
        )
        if not r.ok:
            frappe.log_error(r.text, f"Telegram sendDocument Error (chat_id={chat_id})")
        return r.ok
    except Exception as e:
        frappe.log_error(str(e), "Telegram sendDocument Error")
        return False


def answer_callback(callback_query_id, text=""):
    token = get_bot_token()
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=5
        )
    except Exception:
        pass


# ─── Klaviatura ───────────────────────────────────────────────────────────────

def main_menu_keyboard():
    return {
        "keyboard": [[{"text": "📊 Akt Sverka"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }


def akt_sverka_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "📅 2 hafta", "callback_data": "aks:2w"},
                {"text": "📅 1 oy",    "callback_data": "aks:1m"}
            ],
            [
                {"text": "📅 3 oy",    "callback_data": "aks:3m"},
                {"text": "📅 Hammasi", "callback_data": "aks:all"}
            ]
        ]
    }


# ─── Holat (state) boshqaruv ─────────────────────────────────────────────────

CACHE_PREFIX = "tg_state:"
CACHE_TTL = 300


def _set_state(chat_id, state):
    frappe.cache().set_value(f"{CACHE_PREFIX}{chat_id}", state, expires_in_sec=CACHE_TTL)


def _get_state(chat_id):
    return frappe.cache().get_value(f"{CACHE_PREFIX}{chat_id}") or ""


def _clear_state(chat_id):
    frappe.cache().delete_value(f"{CACHE_PREFIX}{chat_id}")


# ─── Telefon va party qidirish ───────────────────────────────────────────────

def normalize_phone(phone):
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    return digits[-9:] if len(digits) >= 9 else digits


def find_party_by_phone(phone):
    normalized = normalize_phone(phone)
    if not normalized:
        return None

    for doctype in ["Customer", "Supplier"]:
        name_field = "customer_name" if doctype == "Customer" else "supplier_name"

        row = frappe.db.get_value(
            doctype,
            {"contact_number": ["like", f"%{normalized}"]},
            ["name", name_field],
            as_dict=True
        )
        if row:
            return {"doctype": doctype, "name": row.name, "display_name": row.get(name_field) or row.name}

        contact = frappe.db.sql("""
            SELECT dl.link_name
            FROM `tabContact Phone` cp
            JOIN `tabContact` c ON c.name = cp.parent
            JOIN `tabDynamic Link` dl ON dl.parent = c.name
            WHERE cp.phone LIKE %s
              AND dl.link_doctype = %s
              AND dl.parenttype = 'Contact'
            LIMIT 1
        """, (f"%{normalized}%", doctype), as_dict=True)

        if contact:
            party_name = contact[0].link_name
            display = frappe.db.get_value(doctype, party_name, name_field) or party_name
            return {"doctype": doctype, "name": party_name, "display_name": display}

    return None


def find_party_by_chat_id(chat_id):
    """chat_id bo'yicha Customer yoki Supplier topish"""
    chat_id_str = str(chat_id)
    for doctype in ["Customer", "Supplier"]:
        name_field = "customer_name" if doctype == "Customer" else "supplier_name"
        row = frappe.db.get_value(
            doctype,
            {"telegram_chat_id": chat_id_str},
            ["name", name_field],
            as_dict=True
        )
        if row:
            return {
                "doctype": doctype,
                "name": row.name,
                "display_name": row.get(name_field) or row.name
            }
    return None


def get_chat_id_for_party(party_type, party):
    """Notification uchun chat_id olish"""
    if party_type in ("Customer", "Supplier"):
        return frappe.db.get_value(party_type, party, "telegram_chat_id")
    return frappe.db.get_value(
        "Telegram Bot Party",
        {"party_type": party_type, "party": party, "is_registered": 1},
        "telegram_chat_id"
    )


# ─── Akt Sverka PDF ───────────────────────────────────────────────────────────

def _date_range(period_code):
    t = getdate(today())
    if period_code == "2w":
        return str(add_days(t, -14)), str(t)
    elif period_code == "1m":
        return str(add_months(t, -1)), str(t)
    elif period_code == "3m":
        return str(add_months(t, -3)), str(t)
    else:
        return "2000-01-01", str(t)


def generate_akt_sverka_pdf(party_type, party_name, from_date, to_date):
    """Akt Sverka PDF bytes qaytaradi"""
    import os
    from weasyprint import HTML as WeasyHTML
    from ext_accounts.ruxsora_app.report.akt_sverka.akt_sverka import execute

    filters = {
        "party_type": party_type,
        "party": party_name,
        "from_date": from_date,
        "to_date": to_date
    }

    result = execute(filters)
    data = result[1]

    if not data or len(data) <= 1:
        return None

    opening_balance = flt(data[0].get("balance", 0))
    total_row = [r for r in data if r.get("voucher_type") == "Total"]
    closing_balance = flt(total_row[0].get("balance", 0)) if total_row else flt(data[-1].get("balance", 0))

    company = (
        frappe.defaults.get_user_default("company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
        or ""
    )

    context = {
        "data": data,
        "party": party_name,
        "party_type": party_type,
        "from_date": from_date,
        "to_date": to_date,
        "company": company,
        "opening_credit": opening_balance if opening_balance > 0 else 0,
        "opening_debit": abs(opening_balance) if opening_balance < 0 else 0,
        "goods_credit":    sum(flt(r.get("credit", 0)) for r in data if r.get("voucher_type") == "Purchase Invoice"),
        "goods_debit":     sum(flt(r.get("debit",  0)) for r in data if r.get("voucher_type") == "Sales Invoice"),
        "money_credit":    sum(flt(r.get("credit", 0)) for r in data if r.get("voucher_type") == "Payment Entry"),
        "money_debit":     sum(flt(r.get("debit",  0)) for r in data if r.get("voucher_type") == "Payment Entry"),
        "accruals_credit": sum(flt(r.get("credit", 0)) for r in data if r.get("voucher_type") == "Journal Entry"),
        "accruals_debit":  sum(flt(r.get("debit",  0)) for r in data if r.get("voucher_type") == "Journal Entry"),
        "closing_credit":  closing_balance if closing_balance > 0 else 0,
        "closing_debit":   abs(closing_balance) if closing_balance < 0 else 0,
    }

    template_path = os.path.join(
        frappe.get_app_path("ext_accounts"),
        "ruxsora_app", "report", "akt_sverka", "akt_sverka_pdf.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        html = frappe.render_template(f.read(), context)

    return WeasyHTML(string=html).write_pdf()


def handle_akt_sverka(chat_id, callback_query_id, period_code, party_type, party_name, display_name):
    """Akt Sverka PDF generatsiya va yuborish (queue da ishlaydi)"""
    answer_callback(callback_query_id, "Hisobot tayyorlanmoqda...")
    send_message(chat_id, "⏳ <b>Akt Sverka tayyorlanmoqda...</b>")

    try:
        from_date, to_date = _date_range(period_code)
        pdf_bytes = generate_akt_sverka_pdf(party_type, party_name, from_date, to_date)

        if not pdf_bytes or len(pdf_bytes) < 2000:
            send_message(chat_id, "ℹ️ Bu davrda tranzaksiyalar topilmadi.")
            return

        labels = {"2w": "2 hafta", "1m": "1 oy", "3m": "3 oy", "all": "Barcha vaqt"}
        caption = (
            f"📊 <b>Akt Sverka</b>\n"
            f"👤 {display_name}\n"
            f"📅 {from_date} — {to_date}\n"
            f"⏱ Davr: {labels.get(period_code, period_code)}"
        )
        filename = f"Akt_Sverka_{party_name}_{from_date}_{to_date}.pdf"
        send_document(chat_id, pdf_bytes, filename, caption)

    except Exception as e:
        frappe.log_error(str(e), "Akt Sverka PDF Error")
        send_message(chat_id, "❌ Hisobot tayyorlashda xato. Admin bilan bog'laning.")


# ─── Webhook handler ─────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def handle_update():
    """Telegram webhook endpoint"""
    try:
        data = frappe.request.get_json(force=True)
        if not data:
            return {"ok": True}

        cq = data.get("callback_query")
        if cq:
            _handle_callback(cq)
            return {"ok": True}

        msg = data.get("message")
        if not msg:
            return {"ok": True}

        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        _handle_message(chat_id, text)

    except Exception as e:
        frappe.log_error(str(e), "Telegram Webhook Error")

    return {"ok": True}


def _handle_callback(cq):
    chat_id = cq["message"]["chat"]["id"]
    cb_id   = cq["id"]
    cbd     = cq.get("data", "")

    if cbd.startswith("aks:"):
        period_code = cbd.split(":")[1]
        party = find_party_by_chat_id(chat_id)
        if not party:
            answer_callback(cb_id, "Siz tizimda topilmadingiz!")
            return
        frappe.enqueue(
            "ext_accounts.telegram_bot.handle_akt_sverka",
            chat_id=chat_id,
            callback_query_id=cb_id,
            period_code=period_code,
            party_type=party["doctype"],
            party_name=party["name"],
            display_name=party["display_name"],
            queue="long",
            is_async=True
        )


def _handle_message(chat_id, text):
    party = find_party_by_chat_id(chat_id)

    if text == "/start" or text.startswith("/start "):
        if party:
            send_message(
                chat_id,
                f"✅ Siz allaqachon ro'yxatdansiz!\n\n👤 <b>{party['display_name']}</b>",
                reply_markup=main_menu_keyboard()
            )
        else:
            _set_state(chat_id, "awaiting_phone")
            send_message(
                chat_id,
                "👋 Salom! Tizimga kirish uchun telefon raqamingizni yuboring.\n\n"
                "📱 Masalan: <code>998901234567</code> yoki <code>901234567</code>"
            )
        return

    if text == "📊 Akt Sverka":
        if not party:
            send_message(chat_id, "❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return
        send_message(
            chat_id,
            "📊 <b>Akt Sverka</b>\n\nQaysi davr uchun hisobot kerak?",
            reply_markup=akt_sverka_keyboard()
        )
        return

    state = _get_state(chat_id)
    if state == "awaiting_phone":
        found = find_party_by_phone(text)
        if found:
            frappe.db.set_value(found["doctype"], found["name"], "telegram_chat_id", str(chat_id))
            frappe.db.commit()
            _clear_state(chat_id)
            send_message(
                chat_id,
                f"✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
                f"👤 <b>{found['display_name']}</b>\n\n"
                f"Endi tranzaksiyalar haqida avtomatik xabar olasiz.",
                reply_markup=main_menu_keyboard()
            )
        else:
            send_message(
                chat_id,
                "❌ Bu telefon raqam tizimda topilmadi.\n\n"
                "Boshqa raqam kiriting yoki admin bilan bog'laning."
            )
        return

    if not party:
        _set_state(chat_id, "awaiting_phone")
        send_message(
            chat_id,
            "Telefon raqamingizni yuboring:\n\n📱 Masalan: <code>998901234567</code>"
        )


# ─── Webhook sozlash ─────────────────────────────────────────────────────────

@frappe.whitelist()
def set_webhook(webhook_url=None):
    token = get_bot_token()
    if not token:
        frappe.throw(_("Avval Telegram bot tokenini kiriting"))
    if not webhook_url:
        name = frappe.db.get_value("Telegram Settings", {}, "name")
        webhook_url = frappe.db.get_value("Telegram Settings", name, "webhook_url")
    if not webhook_url:
        frappe.throw(_("Webhook URL kiritilmagan"))
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url}, timeout=10
        )
        result = r.json()
        if result.get("ok"):
            frappe.msgprint(_("Webhook o'rnatildi: {0}").format(webhook_url))
        else:
            frappe.throw(_("Xato: {0}").format(result.get("description")))
        return result
    except requests.RequestException as e:
        frappe.throw(str(e))


@frappe.whitelist()
def delete_webhook():
    token = get_bot_token()
    if not token:
        frappe.throw(_("Avval Telegram bot tokenini kiriting"))
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10)
        result = r.json()
        if result.get("ok"):
            frappe.msgprint(_("Webhook o'chirildi"))
        return result
    except requests.RequestException as e:
        frappe.throw(str(e))
