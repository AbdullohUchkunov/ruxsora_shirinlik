# Copyright (c) 2025, abdulloh and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from ext_accounts.overrides.account_hooks import should_create_rashody
from ext_accounts.ruxsora_app.doctype.kassa.kassa import (
	find_indirect_expense_group,
	get_exchange_rate,
	get_transfer_accounts,
	is_under_indirect_expense_group,
)

TEST_PREFIX = "_Test Kassa"


def _get_company():
	return frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")


def _get_asset_group(company):
	"""Testdagi kassa hisoblari uchun istalgan Asset guruh hisobi"""
	return frappe.db.get_value(
		"Account", {"company": company, "is_group": 1, "root_type": "Asset"}, "name", order_by="lft desc"
	)


def _make_account(company, parent, account_name, account_type=None, currency=None, is_group=0):
	return frappe.get_doc(
		{
			"doctype": "Account",
			"company": company,
			"parent_account": parent,
			"account_name": f"{TEST_PREFIX} {account_name}",
			"account_type": account_type,
			"account_currency": currency,
			"is_group": is_group,
		}
	).insert(ignore_permissions=True).name


class TestKassaExchangeRate(FrappeTestCase):
	def test_reverse_rate_keeps_precision(self):
		"""Faqat USD->UZS kursi bo'lsa, UZS->USD teskari kurs 0.0001 ga yaxlitlanmasligi kerak"""
		frappe.get_doc(
			{
				"doctype": "Currency Exchange",
				"date": "2001-01-01",
				"from_currency": "USD",
				"to_currency": "UZS",
				"exchange_rate": 12200,
				"for_buying": 1,
				"for_selling": 1,
			}
		).insert(ignore_permissions=True)

		rate = get_exchange_rate("UZS", "USD", "2001-01-02")

		self.assertAlmostEqual(rate, 1 / 12200, places=9)
		self.assertNotEqual(rate, 0.0001)


class TestKassaTransfer(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _get_company()
		parent = _get_asset_group(cls.company)
		cls.uzs_cash = _make_account(cls.company, parent, "Cash UZS", "Cash", "UZS")
		cls.uzs_bank = _make_account(cls.company, parent, "Bank UZS", "Bank", "UZS")
		cls.usd_cash = _make_account(cls.company, parent, "Cash USD", "Cash", "USD")
		cls.uzs_other = _make_account(cls.company, parent, "Receivable-like UZS", None, "UZS")

	def _transfer_doc(self, cash_account_to):
		doc = frappe.new_doc("Kassa")
		doc.company = self.company
		doc.transaction_type = "Перемещения"
		doc.cash_account = self.uzs_cash
		doc.cash_account_currency = "UZS"
		doc.cash_account_to = cash_account_to
		return doc

	def test_query_lists_all_cash_and_bank_accounts_of_same_currency(self):
		rows = get_transfer_accounts(
			"Account",
			TEST_PREFIX,
			"name",
			0,
			50,
			{"company": self.company, "currency": "UZS", "exclude_account": self.uzs_cash},
		)
		names = [r[0] for r in rows]

		self.assertIn(self.uzs_bank, names)
		self.assertNotIn(self.uzs_cash, names)  # manba hisobi o'zi chiqmaydi
		self.assertNotIn(self.usd_cash, names)  # boshqa valyuta
		self.assertNotIn(self.uzs_other, names)  # kassa/bank emas

	def test_query_without_source_currency_returns_nothing(self):
		self.assertEqual(
			get_transfer_accounts("Account", "", "name", 0, 50, {"company": self.company}), []
		)

	def test_validate_transfer_accepts_same_currency(self):
		self._transfer_doc(self.uzs_bank).validate_transfer()

	def test_validate_transfer_rejects_other_currency(self):
		with self.assertRaises(frappe.ValidationError):
			self._transfer_doc(self.usd_cash).validate_transfer()

	def test_validate_transfer_rejects_same_account(self):
		with self.assertRaises(frappe.ValidationError):
			self._transfer_doc(self.uzs_cash).validate_transfer()

	def test_validate_transfer_rejects_non_cash_account(self):
		with self.assertRaises(frappe.ValidationError):
			self._transfer_doc(self.uzs_other).validate_transfer()

	def test_set_cash_account_keeps_selected_target_for_transfer(self):
		doc = self._transfer_doc(self.uzs_bank)
		doc.mode_of_payment = None
		doc.mode_of_payment_to = "Cash USD"

		doc.set_cash_account()

		self.assertEqual(doc.cash_account_to, self.uzs_bank)
		self.assertIsNone(doc.mode_of_payment_to)


class TestIndirectExpenseGroup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _get_company()
		cls.group = find_indirect_expense_group(cls.company)

	def setUp(self):
		if not self.group:
			self.skipTest("Indirect Expenses group not found")

	def test_group_itself_and_nested_subgroup_are_inside(self):
		subgroup = _make_account(self.company, self.group.name, "Sub Expenses", is_group=1)

		self.assertTrue(is_under_indirect_expense_group(self.group.name, self.company))
		self.assertTrue(is_under_indirect_expense_group(subgroup, self.company))

		leaf = frappe._dict(
			parent_account=subgroup, company=self.company, is_group=0, root_type="Expense", disabled=0
		)
		self.assertTrue(should_create_rashody(leaf))

	def test_account_outside_group_is_rejected(self):
		asset_group = _get_asset_group(self.company)
		self.assertFalse(is_under_indirect_expense_group(asset_group, self.company))

		leaf = frappe._dict(
			parent_account=asset_group, company=self.company, is_group=0, root_type="Expense", disabled=0
		)
		self.assertFalse(should_create_rashody(leaf))

	def test_group_and_disabled_accounts_are_skipped(self):
		base = dict(parent_account=self.group.name, company=self.company, root_type="Expense")
		self.assertFalse(should_create_rashody(frappe._dict(base, is_group=1, disabled=0)))
		self.assertFalse(should_create_rashody(frappe._dict(base, is_group=0, disabled=1)))


class TestKassaJournalEntryDirection(FrappeTestCase):
	"""Дивиденд / Расходы: Приход kassani debet, Расход kassani kredit qilishi kerak"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _get_company()
		cls.dividend_account = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "3200", "is_group": 0}, "name"
		)
		group = find_indirect_expense_group(cls.company)
		cls.expense_account = group and frappe.db.get_value(
			"Account",
			{
				"company": cls.company,
				"is_group": 0,
				"disabled": 0,
				"lft": [">", group.lft],
				"rgt": ["<", group.rgt],
			},
			"name",
		)

	def _submit(self, transaction_type, party_type, mode_of_payment, **extra):
		from ext_accounts.ruxsora_app.doctype.kassa.kassa import get_cash_account

		if not get_cash_account(mode_of_payment, self.company):
			self.skipTest(f"{mode_of_payment} has no cash account")

		kassa = frappe.get_doc(
			{
				"doctype": "Kassa",
				"company": self.company,
				"date": frappe.utils.today(),
				"transaction_type": transaction_type,
				"party_type": party_type,
				"mode_of_payment": mode_of_payment,
				"amount": 1000,
				**extra,
			}
		).insert(ignore_permissions=True)
		kassa.submit()

		je = frappe.get_doc("Journal Entry", {"cheque_no": kassa.name, "docstatus": 1})
		rows = {row.account: row for row in je.accounts}
		return kassa, rows

	def _assert_direction(self, kassa, rows, counter_account, cash_is_debit):
		cash, counter = rows[kassa.cash_account], rows[counter_account]
		if cash_is_debit:
			self.assertEqual(cash.debit_in_account_currency, 1000)
			self.assertGreater(counter.credit, 0)
			self.assertEqual(cash.credit + counter.debit, 0)
		else:
			self.assertEqual(cash.credit_in_account_currency, 1000)
			self.assertGreater(counter.debit, 0)
			self.assertEqual(cash.debit + counter.credit, 0)
		self.assertEqual(cash.debit + cash.credit, counter.debit + counter.credit)

	def test_dividend_receipt_debits_cash(self):
		if not self.dividend_account:
			self.skipTest("3200 not found")
		for mop in ("Cash USD", "Cash UZS"):
			with self.subTest(mop=mop):
				kassa, rows = self._submit("Приход", "Дивиденд", mop)
				self._assert_direction(kassa, rows, self.dividend_account, cash_is_debit=True)

	def test_dividend_payment_credits_cash(self):
		if not self.dividend_account:
			self.skipTest("3200 not found")
		for mop in ("Cash USD", "Cash UZS"):
			with self.subTest(mop=mop):
				kassa, rows = self._submit("Расход", "Дивиденд", mop)
				self._assert_direction(kassa, rows, self.dividend_account, cash_is_debit=False)

	def test_expense_receipt_debits_cash(self):
		if not self.expense_account:
			self.skipTest("no Indirect Expenses ledger")
		for mop in ("Cash USD", "Cash UZS"):
			with self.subTest(mop=mop):
				kassa, rows = self._submit("Приход", "Расходы", mop, expense_account=self.expense_account)
				self._assert_direction(kassa, rows, self.expense_account, cash_is_debit=True)

	def test_expense_payment_credits_cash(self):
		if not self.expense_account:
			self.skipTest("no Indirect Expenses ledger")
		for mop in ("Cash USD", "Cash UZS"):
			with self.subTest(mop=mop):
				kassa, rows = self._submit("Расход", "Расходы", mop, expense_account=self.expense_account)
				self._assert_direction(kassa, rows, self.expense_account, cash_is_debit=False)
