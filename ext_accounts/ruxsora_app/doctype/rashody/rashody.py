# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from ext_accounts.ruxsora_app.doctype.kassa.kassa import (
	get_indirect_expense_group,
	is_under_indirect_expense_group,
)


class Rashody(Document):
	def validate(self):
		"""Validate that expense_account is inside the company's Indirect Expenses (5200) group"""
		if self.expense_account:
			acc = frappe.get_doc("Account", self.expense_account)

			# Must be inside Indirect Expenses (any depth)
			if not is_under_indirect_expense_group(acc.parent_account, acc.company):
				group = get_indirect_expense_group(acc.company)
				frappe.throw(_("Account must be inside '{0}'").format(group.name))

			# Must be Expense type
			if acc.root_type != "Expense":
				frappe.throw(_("Account {0} must be an Expense account").format(self.expense_account))

			# Cannot be group
			if acc.is_group:
				frappe.throw(_("Account {0} cannot be a group account").format(self.expense_account))

			# Set account_name and company
			self.account_name = acc.account_name
			self.company = acc.company
