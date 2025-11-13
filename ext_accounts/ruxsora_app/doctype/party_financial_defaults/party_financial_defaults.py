# -*- coding: utf-8 -*-
# Copyright (c) 2024, Ruxsora and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PartyFinancialDefaults(Document):
	def validate(self):
		"""Validate the Party Financial Defaults"""
		self.validate_party_exists()
		self.validate_accounts()
		self.check_duplicate()
	
	def validate_party_exists(self):
		"""Ensure party exists in the system"""
		if self.party_type and self.party:
			# Check if party exists in the given party type
			if not frappe.db.exists(self.party_type, self.party):
				frappe.throw(f"Party {self.party} does not exist in {self.party_type}")
	
	def validate_accounts(self):
		"""Validate that accounts belong to the selected company"""
		if self.credit_to:
			account_company = frappe.db.get_value('Account', self.credit_to, 'company')
			if account_company != self.company:
				frappe.throw(f'Credit To account must belong to {self.company}')
		
		if self.debit_to:
			account_company = frappe.db.get_value('Account', self.debit_to, 'company')
			if account_company != self.company:
				frappe.throw(f'Debit To account must belong to {self.company}')
	
	def check_duplicate(self):
		"""Check if a record already exists for this party and company"""
		existing = frappe.db.get_value(
			'Party Financial Defaults',
			{
				'party': self.party,
				'party_type': self.party_type,
				'company': self.company,
				'name': ['!=', self.name]
			},
			'name'
		)

		if existing:
			frappe.throw(f'Party Financial Defaults already exists for {self.party} in {self.company}: {existing}')


@frappe.whitelist()
def get_party_financial_defaults(party, party_type, company):
	"""
	Get party financial defaults for a given party and company
	This function can be called from client-side scripts
	"""
	if not party or not party_type or not company:
		return {}
	
	defaults = frappe.db.get_value(
		'Party Financial Defaults',
		{
			'party': party,
			'party_type': party_type,
			'company': company
		},
		['currency', 'credit_to', 'debit_to'],
		as_dict=True
	)
	
	return defaults or {}


def apply_party_defaults(doc, method=None):
	"""
	Generic function to apply party financial defaults
	This can be called from hooks for different doctypes
	"""
	party_field = None
	party_type_field = None

	# Determine party field based on doctype
	if doc.doctype in ['Purchase Invoice', 'Purchase Receipt', 'Purchase Order']:
		party_field = 'supplier'
		party_type_field = 'Supplier'
	elif doc.doctype in ['Sales Invoice', 'Delivery Note', 'Sales Order']:
		party_field = 'customer'
		party_type_field = 'Customer'
	elif doc.doctype == 'Payment Entry':
		party_field = 'party'
		party_type_field = doc.party_type
	else:
		return

	# Get party value
	party = doc.get(party_field)
	if not party or not doc.company:
		return

	# Debug logging
	frappe.logger().debug(f"[Party Defaults] Applying defaults for {doc.doctype} - Party: {party}, Company: {doc.company}")

	# Get party financial defaults
	defaults = get_party_financial_defaults(party, party_type_field, doc.company)
	
	if not defaults:
		frappe.logger().debug(f"[Party Defaults] No defaults found for {party}")
		return

	# Debug: Show what we found
	frappe.logger().debug(f"[Party Defaults] Found defaults: {defaults}")

	# Apply defaults based on doctype - always override
	if doc.doctype in ['Purchase Invoice', 'Purchase Receipt', 'Sales Invoice', 'Delivery Note']:
		# Set currency - always override
		if defaults.get('currency'):
			frappe.logger().debug(f"[Party Defaults] Setting currency to {defaults.get('currency')}")
			doc.currency = defaults.get('currency')

		# Set credit_to for purchase documents - always override
		if doc.doctype == 'Purchase Invoice' and defaults.get('credit_to'):
			frappe.logger().debug(f"[Party Defaults] Setting credit_to to {defaults.get('credit_to')}")
			doc.credit_to = defaults.get('credit_to')

		# Set debit_to for sales documents - always override
		if doc.doctype == 'Sales Invoice' and defaults.get('debit_to'):
			doc.debit_to = defaults.get('debit_to')

	elif doc.doctype == 'Payment Entry':
		# For Payment Entry - always override
		if doc.payment_type == 'Receive' and party_type_field == 'Customer':
			# Set paid_from (customer's debit account)
			if defaults.get('debit_to'):
				doc.paid_from = defaults.get('debit_to')

			# Set paid_from_account_currency
			if defaults.get('currency'):
				doc.paid_from_account_currency = defaults.get('currency')

		elif doc.payment_type == 'Pay' and party_type_field == 'Supplier':
			# Set paid_to (supplier's credit account)
			if defaults.get('credit_to'):
				doc.paid_to = defaults.get('credit_to')

			# Set paid_to_account_currency
			if defaults.get('currency'):
				doc.paid_to_account_currency = defaults.get('currency')