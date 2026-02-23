# ext_accounts/overrides/journal_entry_override.py
"""
Journal Entry override to fix Exchange Rate Revaluation JV creation.

Problem:
  When creating a Journal Entry from Exchange Rate Revaluation (ACC-ERR-XXXX),
  the last row (gain/loss account) can have both debit and credit = 0
  when gain_loss_unbooked == 0 (journal is already balanced).

  The standard validate_debit_credit_amount() skips this check only for
  voucher_type == "Exchange Gain Or Loss" with multi_currency=1,
  but NOT for voucher_type == "Exchange Rate Revaluation".

Fix:
  Extend the exception to also cover "Exchange Rate Revaluation" + multi_currency.
  Zero rows are harmless in this context since set_amounts_in_company_currency()
  handles the actual balancing.
"""
import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry

# Voucher types that use multi-currency and may have zero-amount rows
MULTI_CURRENCY_VOUCHER_TYPES = ("Exchange Gain Or Loss", "Exchange Rate Revaluation")


class JournalEntryOverride(JournalEntry):

    def validate_debit_credit_amount(self):
        """
        Override to allow zero-amount rows for Exchange Rate Revaluation
        multi-currency journal entries (same logic as Exchange Gain Or Loss).
        """
        if not (self.voucher_type in MULTI_CURRENCY_VOUCHER_TYPES and self.multi_currency):
            for d in self.get("accounts"):
                if not flt(d.debit) and not flt(d.credit):
                    frappe.throw(
                        _("Row {0}: Both Debit and Credit values cannot be zero").format(d.idx)
                    )
