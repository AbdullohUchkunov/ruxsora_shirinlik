// Purchase Invoice - Client Script
// ext_accounts app uchun
// File: ext_accounts/public/js/purchase_invoice.js

frappe.ui.form.on('Purchase Invoice', {
	onload: function(frm) {
		// Store defaults for later use
		frm.party_defaults = null;
	},

	supplier: function(frm) {
		if (frm.doc.supplier && frm.doc.company) {
			// Call server-side method to get defaults
			frappe.call({
				method: 'ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.get_party_financial_defaults',
				args: {
					party: frm.doc.supplier,
					party_type: 'Supplier',
					company: frm.doc.company
				},
				debounce: false,
				callback: function(r) {
					if (r.message) {
						// Store defaults
						frm.party_defaults = r.message;

						// Apply after a short delay to override ERPNext's get_party_details
						setTimeout(function() {
							if (frm.party_defaults.currency) {
								frm.set_value('currency', frm.party_defaults.currency);
								frm.set_df_property('currency', 'read_only', 1);
								frm.refresh_field('currency');
							}

							if (frm.party_defaults.credit_to) {
								frm.set_value('credit_to', frm.party_defaults.credit_to);
								frm.set_df_property('credit_to', 'read_only', 1);
								frm.refresh_field('credit_to');
							}
						}, 500); // Wait 500ms for ERPNext's code to finish
					}
				}
			});
		}
	},

	company: function(frm) {
		if (frm.doc.supplier) {
			frm.trigger('supplier');
		}
	}
});