// Purchase Receipt - Client Script
// ext_accounts app uchun
// File: ext_accounts/public/js/purchase_receipt.js

frappe.ui.form.on('Purchase Receipt', {
	onload: function(frm) {
		frm.party_defaults = null;
	},

	supplier: function(frm) {
		if (frm.doc.supplier && frm.doc.company) {
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
						frm.party_defaults = r.message;

						// Apply after delay to override ERPNext's code
						setTimeout(function() {
							if (frm.party_defaults.currency) {
								frm.set_value('currency', frm.party_defaults.currency);
								frm.set_df_property('currency', 'read_only', 1);
								frm.refresh_field('currency');
							}
						}, 500);
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