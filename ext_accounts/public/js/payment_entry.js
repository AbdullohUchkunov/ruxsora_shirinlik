// Payment Entry - Client Script
// ext_accounts app uchun
// File: ext_accounts/public/js/payment_entry.js

frappe.ui.form.on('Payment Entry', {
	onload: function(frm) {
		frm.party_defaults = null;
	},

	party: function(frm) {
		if (frm.doc.party && frm.doc.party_type && frm.doc.company) {
			frappe.call({
				method: 'ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.get_party_financial_defaults',
				args: {
					party: frm.doc.party,
					party_type: frm.doc.party_type,
					company: frm.doc.company
				},
				debounce: false,
				callback: function(r) {
					if (r.message) {
						frm.party_defaults = r.message;

						// Apply after delay to override ERPNext's code
						setTimeout(function() {
							// For Receive (from Customer)
							if (frm.doc.payment_type === 'Receive') {
								if (frm.party_defaults.debit_to) {
									frm.set_value('paid_from', frm.party_defaults.debit_to);
									frm.set_df_property('paid_from', 'read_only', 1);
									frm.refresh_field('paid_from');
								}

								if (frm.party_defaults.currency) {
									frm.set_value('paid_from_account_currency', frm.party_defaults.currency);
									frm.set_df_property('paid_from_account_currency', 'read_only', 1);
									frm.refresh_field('paid_from_account_currency');
								}
							}

							// For Pay (to Supplier)
							if (frm.doc.payment_type === 'Pay') {
								if (frm.party_defaults.credit_to) {
									frm.set_value('paid_to', frm.party_defaults.credit_to);
									frm.set_df_property('paid_to', 'read_only', 1);
									frm.refresh_field('paid_to');
								}

								if (frm.party_defaults.currency) {
									frm.set_value('paid_to_account_currency', frm.party_defaults.currency);
									frm.set_df_property('paid_to_account_currency', 'read_only', 1);
									frm.refresh_field('paid_to_account_currency');
								}
							}
						}, 500);
					}
				}
			});
		}
	},

	payment_type: function(frm) {
		if (frm.doc.party) {
			frm.trigger('party');
		}
	},

	company: function(frm) {
		if (frm.doc.party) {
			frm.trigger('party');
		}
	}
});