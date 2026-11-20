import re
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from ext_accounts import telegram_bot

TOKEN = "123456:TEST-token"
HEADER = "X-Telegram-Bot-Api-Secret-Token"


def _headers(value):
	return lambda key, default=None: value if key == HEADER else default


class TestTelegramWebhookSecret(FrappeTestCase):
	def test_secret_matches_telegram_format(self):
		secret = telegram_bot.get_webhook_secret(TOKEN)
		self.assertRegex(secret, re.compile(r"^[A-Za-z0-9_-]{1,256}$"))
		self.assertNotIn(TOKEN, secret)

	@patch.object(telegram_bot, "get_bot_token", return_value=TOKEN)
	def test_request_with_correct_secret_is_accepted(self, _):
		secret = telegram_bot.get_webhook_secret(TOKEN)
		with patch("frappe.get_request_header", _headers(secret)):
			self.assertTrue(telegram_bot.is_valid_webhook_request())

	@patch.object(telegram_bot, "get_bot_token", return_value=TOKEN)
	def test_request_with_wrong_or_missing_secret_is_rejected(self, _):
		for value in (None, "", "forged"):
			with patch("frappe.get_request_header", _headers(value)):
				self.assertFalse(telegram_bot.is_valid_webhook_request())

	@patch.object(telegram_bot, "get_bot_token", return_value=None)
	def test_request_is_rejected_when_bot_not_configured(self, _):
		with patch("frappe.get_request_header", _headers("anything")):
			self.assertFalse(telegram_bot.is_valid_webhook_request())
