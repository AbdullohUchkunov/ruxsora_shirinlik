# ext_accounts/overrides/payment_entry_rashody.py
"""
Payment Entry override for Rashody party type.
Handles direct expense payments without party accounts.

Logic:
- Pay:   DR Expense Account (from party field) / CR Bank
- Receive: DR Bank / CR Expense Account (from party field)
"""
import frappe
from frappe import _
from frappe.utils import flt, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from erpnext.setup.utils import get_exchange_rate


class PaymentEntryRashody(PaymentEntry):
    
    def validate(self):
        """Override validate to handle Rashody party type"""
        if self.party_type == "Rashody":
            self.validate_rashody()
            self.validate_mandatory()
            self.set_missing_values()
            self.set_amounts()
            self.apply_taxes()
            self.validate_payment_type()
            self.set_title()
            self.set_remarks()
            self.validate_duplicate_entry()
            self.set_status()
        else:
            super().validate()
    
    def validate_rashody(self):
        """
        Validate Rashody specific fields.
        For Rashody, party field contains Account (not a party DocType).
        """
        if not self.party:
            frappe.throw(_("Please select an Expense Account in Party field"))
        
        # Party = Account name for Rashody
        if not frappe.db.exists("Account", self.party):
            frappe.throw(_("Selected Party '{0}' is not a valid Account").format(self.party))
        
        acc = frappe.get_doc("Account", self.party)
        if acc.root_type != "Expense":
            frappe.throw(_("Account '{0}' must be an Expense account (Root Type: Expense)").format(self.party))
        
        if acc.is_group:
            frappe.throw(_("Account '{0}' cannot be a group account. Please select a ledger account.").format(self.party))
        
        # Set party_name to account_name for Rashody
        self.party_name = acc.account_name
        self.references = []
        
        if self.payment_type == "Pay":
            if not self.paid_amount or self.paid_amount <= 0:
                frappe.throw(_("Paid Amount must be greater than 0"))
            if not self.paid_from:
                frappe.throw(_("Paid From account is mandatory"))
        elif self.payment_type == "Receive":
            if not self.received_amount or self.received_amount <= 0:
                frappe.throw(_("Received Amount must be greater than 0"))
            if not self.paid_to:
                frappe.throw(_("Paid To account is mandatory"))
    
    def set_missing_values(self):
        """Override to handle Rashody"""
        if self.party_type == "Rashody":
            if not self.posting_date:
                self.posting_date = getdate()
            
            if not self.reference_date:
                self.reference_date = self.posting_date
            
            # Set party_name to account_name
            if self.party and frappe.db.exists("Account", self.party):
                self.party_name = frappe.db.get_value("Account", self.party, "account_name")
            
            # Set party_account_currency - required for set_remarks()
            if self.payment_type == "Pay":
                # Pay: Money goes from bank/cash to expense account
                # Party account is the expense account (paid_to)
                self.party_account_currency = self.paid_to_account_currency if hasattr(self, 'paid_to_account_currency') else self.company_currency
                # DON'T set received_amount here - let user fill paid_amount
                # received_amount should remain as entered or 0 by default
            elif self.payment_type == "Receive":
                # Receive: Money comes from expense account to bank/cash
                # Party account is the expense account (paid_from)
                self.party_account_currency = self.paid_from_account_currency if hasattr(self, 'paid_from_account_currency') else self.company_currency
                # DON'T set paid_amount here - let user fill received_amount
                # paid_amount should remain as entered or 0 by default
            
            self.total_allocated_amount = 0
            self.base_total_allocated_amount = 0
            
            # Calculate unallocated amount based on payment type
            if self.payment_type == "Pay":
                self.unallocated_amount = flt(self.paid_amount)
            else:
                self.unallocated_amount = flt(self.received_amount)
            
            return
        
        super().set_missing_values()
    
    def set_amounts(self):
        """Override amount calculation for Rashody"""
        if self.party_type == "Rashody":
            company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
            
            if self.payment_type == "Pay":
                # Pay: User enters paid_amount, system calculates received_amount
                # paid_from (Bank/Cash) → paid_to (Expense Account)
                
                if self.paid_from and self.paid_to:
                    paid_from_acc = frappe.get_doc("Account", self.paid_from)
                    paid_to_acc = frappe.get_doc("Account", self.paid_to)
                    
                    paid_from_currency = paid_from_acc.account_currency or company_currency
                    paid_to_currency = paid_to_acc.account_currency or company_currency
                    
                    # Calculate base_paid_amount (in company currency)
                    if paid_from_currency != company_currency:
                        source_exchange_rate = get_exchange_rate(paid_from_currency, company_currency, self.posting_date)
                        self.source_exchange_rate = source_exchange_rate
                        self.base_paid_amount = flt(self.paid_amount) * source_exchange_rate
                    else:
                        self.source_exchange_rate = 1.0
                        self.base_paid_amount = flt(self.paid_amount)
                    
                    # Calculate received_amount (in paid_to currency)
                    if paid_from_currency == paid_to_currency:
                        # Same currency: received = paid
                        self.received_amount = self.paid_amount
                        self.base_received_amount = self.base_paid_amount
                        self.target_exchange_rate = self.source_exchange_rate
                    else:
                        # Different currencies: convert base_paid_amount to paid_to currency
                        if paid_to_currency != company_currency:
                            target_exchange_rate = get_exchange_rate(paid_to_currency, company_currency, self.posting_date)
                            self.target_exchange_rate = target_exchange_rate
                            self.received_amount = flt(self.base_paid_amount) / target_exchange_rate
                        else:
                            self.target_exchange_rate = 1.0
                            self.received_amount = self.base_paid_amount
                        
                        self.base_received_amount = self.base_paid_amount
                
                self.unallocated_amount = flt(self.paid_amount)
                
            elif self.payment_type == "Receive":
                # Receive: User enters received_amount, system calculates paid_amount
                # paid_from (Expense Account) → paid_to (Bank/Cash)
                
                if self.paid_from and self.paid_to:
                    paid_from_acc = frappe.get_doc("Account", self.paid_from)
                    paid_to_acc = frappe.get_doc("Account", self.paid_to)
                    
                    paid_from_currency = paid_from_acc.account_currency or company_currency
                    paid_to_currency = paid_to_acc.account_currency or company_currency
                    
                    # Calculate base_received_amount (in company currency)
                    if paid_to_currency != company_currency:
                        target_exchange_rate = get_exchange_rate(paid_to_currency, company_currency, self.posting_date)
                        self.target_exchange_rate = target_exchange_rate
                        self.base_received_amount = flt(self.received_amount) * target_exchange_rate
                    else:
                        self.target_exchange_rate = 1.0
                        self.base_received_amount = flt(self.received_amount)
                    
                    # Calculate paid_amount (in paid_from currency)
                    if paid_from_currency == paid_to_currency:
                        # Same currency: paid = received
                        self.paid_amount = self.received_amount
                        self.base_paid_amount = self.base_received_amount
                        self.source_exchange_rate = self.target_exchange_rate
                    else:
                        # Different currencies: convert base_received_amount to paid_from currency
                        if paid_from_currency != company_currency:
                            source_exchange_rate = get_exchange_rate(paid_from_currency, company_currency, self.posting_date)
                            self.source_exchange_rate = source_exchange_rate
                            self.paid_amount = flt(self.base_received_amount) / source_exchange_rate
                        else:
                            self.source_exchange_rate = 1.0
                            self.paid_amount = self.base_received_amount
                        
                        self.base_paid_amount = self.base_received_amount
                
                self.unallocated_amount = flt(self.received_amount)
            
            self.total_allocated_amount = 0
            self.base_total_allocated_amount = 0
            self.difference_amount = 0
            
            return
        
        super().set_amounts()
    
    def get_gl_entries(self, against_voucher_type=None, against_voucher=None, 
                       on_cancel=False, update_outstanding="Yes", from_repost=False):
        """Create GL entries for Rashody"""
        if self.party_type != "Rashody":
            return super().get_gl_entries(against_voucher_type, against_voucher, 
                                         on_cancel, update_outstanding, from_repost)
        
        gl_entries = []
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        expense_account = self.party
        expense_acc = frappe.get_doc("Account", expense_account)
        expense_currency = expense_acc.account_currency or company_currency
        
        if self.payment_type == "Pay":
            paid_from_acc = frappe.get_doc("Account", self.paid_from)
            paid_from_currency = paid_from_acc.account_currency or company_currency
            
            if paid_from_currency != company_currency:
                exchange_rate = get_exchange_rate(paid_from_currency, company_currency, self.posting_date)
                base_paid_amount = flt(self.paid_amount) * exchange_rate
            else:
                exchange_rate = 1
                base_paid_amount = flt(self.paid_amount)
            
            gl_entries.append(self.get_gl_dict({
                "account": expense_account,
                "party_type": None,
                "party": None,
                "against": self.paid_from,
                "debit": base_paid_amount,
                "debit_in_account_currency": base_paid_amount if expense_currency == company_currency 
                                             else base_paid_amount / get_exchange_rate(expense_currency, company_currency, self.posting_date),
                "credit": 0,
                "credit_in_account_currency": 0,
                "account_currency": expense_currency,
                "cost_center": self.cost_center or frappe.get_cached_value("Company", self.company, "cost_center"),
                "remarks": self.remarks or f"Expense payment via {self.name}"
            }, item=self))
            
            gl_entries.append(self.get_gl_dict({
                "account": self.paid_from,
                "party_type": None,
                "party": None,
                "against": expense_account,
                "debit": 0,
                "debit_in_account_currency": 0,
                "credit": base_paid_amount,
                "credit_in_account_currency": flt(self.paid_amount),
                "account_currency": paid_from_currency,
                "remarks": self.remarks or f"Expense payment via {self.name}"
            }, item=self))
        
        elif self.payment_type == "Receive":
            paid_to_acc = frappe.get_doc("Account", self.paid_to)
            paid_to_currency = paid_to_acc.account_currency or company_currency
            
            if paid_to_currency != company_currency:
                exchange_rate = get_exchange_rate(paid_to_currency, company_currency, self.posting_date)
                base_received_amount = flt(self.received_amount) * exchange_rate
            else:
                exchange_rate = 1
                base_received_amount = flt(self.received_amount)
            
            gl_entries.append(self.get_gl_dict({
                "account": self.paid_to,
                "party_type": None,
                "party": None,
                "against": expense_account,
                "debit": base_received_amount,
                "debit_in_account_currency": flt(self.received_amount),
                "credit": 0,
                "credit_in_account_currency": 0,
                "account_currency": paid_to_currency,
                "remarks": self.remarks or f"Expense receipt via {self.name}"
            }, item=self))
            
            gl_entries.append(self.get_gl_dict({
                "account": expense_account,
                "party_type": None,
                "party": None,
                "against": self.paid_to,
                "debit": 0,
                "debit_in_account_currency": 0,
                "credit": base_received_amount,
                "credit_in_account_currency": base_received_amount if expense_currency == company_currency 
                                              else base_received_amount / get_exchange_rate(expense_currency, company_currency, self.posting_date),
                "account_currency": expense_currency,
                "cost_center": self.cost_center or frappe.get_cached_value("Company", self.company, "cost_center"),
                "remarks": self.remarks or f"Expense receipt via {self.name}"
            }, item=self))
        
        return gl_entries
    
    def set_title(self):
        """Override title for Rashody"""
        if self.party_type == "Rashody":
            if self.party:
                account_name = frappe.db.get_value("Account", self.party, "account_name")
                self.title = f"{self.payment_type} - {account_name or self.party}"
            else:
                self.title = f"{self.payment_type} - Expense"
        else:
            super().set_title()
