# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Rashody(Document):
	def validate(self):
		"""Validate that expense_account is from 5200 - Indirect Expenses"""
		if self.expense_account:
			acc = frappe.get_doc("Account", self.expense_account)
			
			# Must be under 5200
			if acc.parent_account != "5200 - Indirect Expenses - R":
				frappe.throw(f"Account must be a child of '5200 - Indirect Expenses - R'")
			
			# Must be Expense type
			if acc.root_type != "Expense":
				frappe.throw(f"Account {self.expense_account} must be an Expense account")
			
			# Cannot be group
			if acc.is_group:
				frappe.throw(f"Account {self.expense_account} cannot be a group account")
			
			# Set account_name and company
			self.account_name = acc.account_name
			self.company = acc.company
