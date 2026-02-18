# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import json
import requests
import frappe
from frappe import _


def get_bot_token():
    """Telegram bot tokenini olish"""
    return frappe.db.get_single_value("Telegram Bot Sozlamasi", "telegram_token")


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    """Telegram ga xabar yuborish"""
    token = get_bot_token()
    if not token:
        frappe.log_error("Telegram bot token kiritilmagan", "Telegram Bot")
        return

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10
        )
        if not response.ok:
            frappe.log_error(
                f"Telegram xabar yuborishda xato: {response.text}",
                "Telegram Bot"
            )
    except Exception as e:
        frappe.log_error(f"Telegram so'rovida xato: {str(e)}", "Telegram Bot")


def remove_reply_keyboard(chat_id, text):
    """Reply keyboard ni o'chirish"""
    send_message(chat_id, text, reply_markup={"remove_keyboard": True})


def normalize_phone(phone):
    """Telefon raqamni normallashtirish: faqat raqamlar"""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    # Agar 998 bilan boshlansa, oxirgi 9 raqamni olish
    if len(digits) > 9 and digits.startswith("998"):
        digits = digits[3:]
    elif len(digits) > 9 and digits.startswith("7"):
        digits = digits[1:]
    return digits


def find_party_by_phone(phone):
    """Telefon raqam bo'yicha Telegram Bot Party yozuvini topish"""
    normalized = normalize_phone(phone)
    if not normalized:
        return None

    # Barcha yozuvlarni olish va normalize qilib tekshirish
    all_parties = frappe.db.sql("""
        SELECT name, parent, party_type, party, phone, phone2, telegram_chat_id
        FROM `tabTelegram Bot Party`
        WHERE is_registered = 0 OR is_registered IS NULL
    """, as_dict=True)

    for row in all_parties:
        if normalize_phone(row.phone) == normalized:
            return row
        if row.phone2 and normalize_phone(row.phone2) == normalized:
            return row

    return None


@frappe.whitelist(allow_guest=True)
def handle_update():
    """Telegram webhook endpoint - Telegramdan kelgan yangiliklar"""
    try:
        data = frappe.request.get_json(force=True)
        if not data:
            return {"ok": True}

        message = data.get("message")
        if not message:
            return {"ok": True}

        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        contact = message.get("contact")

        # /start komandasi
        if text == "/start" or text.startswith("/start "):
            send_message(
                chat_id,
                "Salom! Ro'yxatdan o'tish uchun telefon raqamingizni ulashing.",
                reply_markup={
                    "keyboard": [
                        [{"text": "📱 Telefon raqamni ulashish", "request_contact": True}]
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True
                }
            )

        # Telefon raqam ulashildi
        elif contact:
            phone = contact.get("phone_number", "")
            party_row = find_party_by_phone(phone)

            if party_row:
                # chat_id ni saqlash va ro'yxatdan o'tgan deb belgilash
                frappe.db.set_value(
                    "Telegram Bot Party",
                    party_row["name"],
                    {
                        "telegram_chat_id": str(chat_id),
                        "is_registered": 1
                    }
                )
                frappe.db.commit()

                remove_reply_keyboard(
                    chat_id,
                    "✅ Ro'yxatga oldingiz!\n\nEndi tranzaksiyalar haqida xabar olasiz."
                )
            else:
                remove_reply_keyboard(
                    chat_id,
                    "❌ Ro'yxatda mavjud emassiz.\n\nIltimos, admin bilan bog'laning."
                )

        return {"ok": True}

    except Exception as e:
        frappe.log_error(f"Telegram webhook xatosi: {str(e)}", "Telegram Bot")
        return {"ok": True}


@frappe.whitelist()
def set_webhook(webhook_url=None):
    """Telegram webhook manzilini o'rnatish"""
    token = get_bot_token()
    if not token:
        frappe.throw(_("Avval Telegram bot tokenini kiriting"))

    if not webhook_url:
        # Agar URL berilmasa, Sozlamadagi webhook_url dan olish
        webhook_url = frappe.db.get_single_value("Telegram Bot Sozlamasi", "webhook_url")

    if not webhook_url:
        frappe.throw(_("Webhook URL kiritilmagan"))

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url},
            timeout=10
        )
        result = response.json()
        if result.get("ok"):
            frappe.msgprint(_("Webhook muvaffaqiyatli o'rnatildi: {0}").format(webhook_url))
        else:
            frappe.throw(_("Webhook o'rnatishda xato: {0}").format(result.get("description")))
        return result
    except requests.RequestException as e:
        frappe.throw(_("Telegram bilan bog'lanishda xato: {0}").format(str(e)))


@frappe.whitelist()
def delete_webhook():
    """Telegram webhookni o'chirish"""
    token = get_bot_token()
    if not token:
        frappe.throw(_("Avval Telegram bot tokenini kiriting"))

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            timeout=10
        )
        result = response.json()
        if result.get("ok"):
            frappe.msgprint(_("Webhook o'chirildi"))
        return result
    except requests.RequestException as e:
        frappe.throw(_("Telegram bilan bog'lanishda xato: {0}").format(str(e)))


def get_chat_id_for_party(party_type, party):
    """Party uchun telegram chat_id olish"""
    result = frappe.db.get_value(
        "Telegram Bot Party",
        {"party_type": party_type, "party": party, "is_registered": 1},
        "telegram_chat_id"
    )
    return result
