frappe.ui.form.on('Other', {
  party_name(frm) {
    if (!frm.doc.other_name) {
      frm.set_value('other_name', frm.doc.party_name);
    }
  }
});
