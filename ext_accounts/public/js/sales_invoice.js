// Sales Invoice - Client Script
// ext_accounts app uchun
// File: ext_accounts/public/js/sales_invoice.js

frappe.ui.form.on('Sales Invoice', {
	onload: function(frm) {
		frm.party_defaults = null;
	},

	customer: function(frm) {
		if (frm.doc.customer && frm.doc.company) {
			frappe.call({
				method: 'ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.get_party_financial_defaults',
				args: {
					party: frm.doc.customer,
					party_type: 'Customer',
					company: frm.doc.company
				},
				debounce: false,
				callback: function(r) {
					if (r.message) {
						frm.party_defaults = r.message;

						// Apply after delay to override ERPNext's code
						setTimeout(function() {
							if (frm.party_defaults.currency) {
								frm.set_value('currency', frm.party_defaults.currency);
								frm.set_df_property('currency', 'read_only', 1);
								frm.refresh_field('currency');
							}

							if (frm.party_defaults.debit_to) {
								frm.set_value('debit_to', frm.party_defaults.debit_to);
								frm.set_df_property('debit_to', 'read_only', 1);
								frm.refresh_field('debit_to');
							}
						}, 500);
					}
				}
			});
		}
	},

	company: function(frm) {
		if (frm.doc.customer) {
			frm.trigger('customer');
		}
	}
});
