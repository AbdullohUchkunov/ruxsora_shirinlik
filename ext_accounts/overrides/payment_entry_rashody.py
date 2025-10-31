# # ext_accounts/overrides/payment_entry_rashody.py
# import frappe
# from frappe import _
# from frappe.utils import flt, getdate
# from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
# from erpnext.setup.utils import get_exchange_rate
# from erpnext.accounts.utils import get_fiscal_year

# class PaymentEntryRashody(PaymentEntry):
    
#     def validate(self):
#         """Override validate to handle Расходы party type"""
#         if self.party_type == "Расходы":
#             self.validate_rashody()
#             # Skip party validation for Расходы
#             self.validate_payment_type()
#             self.validate_transaction_reference()
#             self.validate_mandatory()
#             self.validate_reference_documents()
#             self.set_missing_ref_details()
#             self.set_missing_values()
#             self.validate_payment_type()
#             self.apply_taxes()
#             self.set_amounts()
#             self.clear_unallocated_reference_document_rows()
#             self.validate_payment_against_negative_invoice()
#             self.validate_transaction_reference()
#             self.set_transaction_reference()
#             self.set_title()
#             self.set_remarks()
#             self.validate_duplicate_entry()
#             self.validate_journal_entry()
#             self.set_status()
#         else:
#             # Standard validation
#             super().validate()
    
#     def validate_rashody(self):
#         """Validate Расходы specific fields"""
#         if not self.expense_account:
#             frappe.throw(_("Expense Account is mandatory for 'Расходы' party type"))
        
#         # Validate expense account
#         acc = frappe.get_doc("Account", self.expense_account)
#         if acc.root_type != "Expense":
#             frappe.throw(_("Account {0} must be an Expense account").format(self.expense_account))
        
#         if acc.is_group:
#             frappe.throw(_("Account {0} cannot be a group account").format(self.expense_account))
        
#         # Clear party fields
#         self.party = None
#         self.party_name = None
#         self.party_account = None
#         self.party_account_currency = None
        
#         # Clear references
#         self.references = []
        
#         # Validate amounts
#         if not self.paid_amount or self.paid_amount <= 0:
#             frappe.throw(_("Paid Amount must be greater than 0"))
    
#     def validate_party(self):
#         """Override party validation for Расходы"""
#         if self.party_type == "Расходы":
#             return
#         super().validate_party()
    
#     def set_party_account(self):
#         """Override to skip party account for Расходы"""
#         if self.party_type == "Расходы":
#             self.party_account = None
#             return
#         super().set_party_account()
    
#     def set_party_account_currency(self):
#         """Override to skip for Расходы"""
#         if self.party_type == "Расходы":
#             self.party_account_currency = None
#             return
#         super().set_party_account_currency()
    
#     def validate_reference_documents(self):
#         """Skip reference validation for Расходы"""
#         if self.party_type == "Расходы":
#             self.references = []
#             return
#         super().validate_reference_documents()
    
#     def get_gl_entries(self, against_voucher_type=None, against_voucher=None, 
#                        on_cancel=False, update_outstanding="Yes", from_repost=False):
#         """
#         Create GL entries for Расходы
#         DR: Expense Account (base currency USD)
#         CR: Bank/Cash Account (account currency, e.g. UZS)
#         """
#         if self.party_type != "Расходы":
#             return super().get_gl_entries(against_voucher_type, against_voucher, 
#                                          on_cancel, update_outstanding, from_repost)
        
#         gl_entries = []
        
#         # Company base currency (USD)
#         company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        
#         # Get account details
#         expense_acc = frappe.get_doc("Account", self.expense_account)
#         expense_currency = expense_acc.account_currency or company_currency
        
#         paid_from_acc = frappe.get_doc("Account", self.paid_from)
#         paid_from_currency = paid_from_acc.account_currency or company_currency
        
#         # Amount in payment currency (e.g., UZS)
#         paid_amount = flt(self.paid_amount)
        
#         # Get exchange rate from payment currency to base currency
#         if paid_from_currency != company_currency:
#             # UZS to USD conversion
#             exchange_rate = get_exchange_rate(
#                 paid_from_currency, 
#                 company_currency, 
#                 self.posting_date
#             )
#             base_paid_amount = paid_amount * exchange_rate
#         else:
#             exchange_rate = 1
#             base_paid_amount = paid_amount
        
#         # DR: Expense Account
#         dr_entry = self.get_gl_dict({
#             "account": self.expense_account,
#             "party_type": None,
#             "party": None,
#             "against": self.paid_from,
#             "debit": base_paid_amount,
#             "debit_in_account_currency": base_paid_amount if expense_currency == company_currency 
#                                          else base_paid_amount / get_exchange_rate(expense_currency, company_currency, self.posting_date),
#             "credit": 0,
#             "credit_in_account_currency": 0,
#             "account_currency": expense_currency,
#             "cost_center": self.cost_center or frappe.get_cached_value("Company", self.company, "cost_center"),
#             "remarks": self.remarks or f"Payment for expenses via {self.name}"
#         })
#         gl_entries.append(dr_entry)
        
#         # CR: Bank/Cash Account
#         cr_entry = self.get_gl_dict({
#             "account": self.paid_from,
#             "party_type": None,
#             "party": None,
#             "against": self.expense_account,
#             "debit": 0,
#             "debit_in_account_currency": 0,
#             "credit": base_paid_amount,
#             "credit_in_account_currency": paid_amount,
#             "account_currency": paid_from_currency,
#             "remarks": self.remarks or f"Payment for expenses via {self.name}"
#         })
#         gl_entries.append(cr_entry)
        
#         return gl_entries
    
#     def set_missing_values(self):
#         """Override to handle Расходы"""
#         if self.party_type == "Расходы":
#             # Set basic values
#             if not self.posting_date:
#                 self.posting_date = getdate()
            
#             if not self.reference_date:
#                 self.reference_date = self.posting_date
            
#             # Set payment type
#             if not self.payment_type:
#                 self.payment_type = "Pay"
            
#             # Clear party related fields
#             self.party = None
#             self.party_name = None
#             self.party_account = None
            
#             # Set amounts
#             if self.paid_amount and not self.received_amount:
#                 self.received_amount = 0
            
#             # Set base amounts
#             company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
#             if self.paid_from:
#                 paid_from_acc = frappe.get_doc("Account", self.paid_from)
#                 paid_from_currency = paid_from_acc.account_currency or company_currency
                
#                 if paid_from_currency != company_currency:
#                     exchange_rate = get_exchange_rate(
#                         paid_from_currency,
#                         company_currency,
#                         self.posting_date
#                     )
#                     self.base_paid_amount = flt(self.paid_amount) * exchange_rate
#                 else:
#                     self.base_paid_amount = flt(self.paid_amount)
            
#             self.base_received_amount = 0
            
#             # Set totals
#             self.total_allocated_amount = 0
#             self.base_total_allocated_amount = 0
#             self.unallocated_amount = flt(self.paid_amount)
            
#             return
        
#         super().set_missing_values()
    
#     def set_amounts(self):
#         """Override amount calculation for Расходы"""
#         if self.party_type == "Расходы":
#             # Simple amount setting for expense payments
#             self.received_amount = 0
#             self.base_received_amount = 0
            
#             # Calculate base amounts
#             if self.paid_from:
#                 company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
#                 paid_from_acc = frappe.get_doc("Account", self.paid_from)
#                 paid_from_currency = paid_from_acc.account_currency or company_currency
                
#                 if paid_from_currency != company_currency:
#                     exchange_rate = get_exchange_rate(
#                         paid_from_currency,
#                         company_currency, 
#                         self.posting_date
#                     )
#                     self.base_paid_amount = flt(self.paid_amount) * exchange_rate
#                 else:
#                     self.base_paid_amount = flt(self.paid_amount)
            
#             # No allocations for expense payments
#             self.total_allocated_amount = 0
#             self.base_total_allocated_amount = 0
#             self.unallocated_amount = flt(self.paid_amount)
#             self.difference_amount = 0
            
#             return
        
#         super().set_amounts()