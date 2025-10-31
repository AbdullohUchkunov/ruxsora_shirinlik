// // ext_accounts/public/js/pe_override_full.js
// console.log("[pe_override_full] LOADED");
// frappe.provide("ext_accounts.pe");

// // --- UI boshqaruv
// ext_accounts.pe.toggle_fields = function (frm) {
//   const is_rashody = frm.doc.party_type === "Расходы";

//   frm.toggle_display("party", !is_rashody);
//   frm.toggle_reqd("party", !is_rashody);

//   frm.toggle_display("party_account", !is_rashody);
//   frm.toggle_reqd("party_account", !is_rashody);

//   if (frm.fields_dict.expense_account) {
//     frm.toggle_display("expense_account", is_rashody);
//     frm.toggle_reqd("expense_account", is_rashody);
//   }

//   frm.toggle_display("references_section", !is_rashody);
//   frm.toggle_display("party_balance", !is_rashody);
//   frm.toggle_display("set_advances", !is_rashody);
//   frm.toggle_display("advances_section", !is_rashody);

//   if (is_rashody) {
//     if (frm.doc.party) frm.set_value("party", null);
//     if (frm.doc.party_account) frm.set_value("party_account", null);
//   }
// };

// // --- Querylar
// ext_accounts.pe.setup_queries = function (frm) {
//   frm.set_query("party_type", function () {
//     return {
//       query: "ext_accounts.overrides.payment_entry_queries.get_party_type",
//       filters: { payment_type: frm.doc.payment_type || "" },
//     };
//   });

//   frm.set_query("expense_account", function () {
//     if (frm.doc.party_type === "Расходы") {
//       return {
//         filters: {
//           root_type: "Expense",
//           is_group: 0,
//           company: frm.doc.company,
//         },
//       };
//     }
//   });

//   frm.set_query("paid_from", function () {
//     return {
//       filters: {
//         account_type: ["in", ["Bank", "Cash"]],
//         is_group: 0,
//         company: frm.doc.company,
//       },
//     };
//   });

//   frm.set_query("paid_to", function () {
//     return {
//       filters: {
//         account_type: ["in", ["Bank", "Cash"]],
//         is_group: 0,
//         company: frm.doc.company,
//       },
//     };
//   });
// };

// // --- set_value ni himoyalovchi guard (core tozalashini bloklaydi)
// ext_accounts.pe.install_guard = function (frm) {
//   if (frm._ext_set_value_patched) return;

//   const _orig_set_value = frm.set_value.bind(frm);
//   frm.set_value = function (field, val) {
//     // Guard oynasi ichida party_type ni tozalashga yo'l qo'ymaymiz
//     if (field === "party_type") {
//       const now = Date.now();
//       if (frm._protect_party_type_until && now < frm._protect_party_type_until) {
//         const is_clearing = (val === "" || val === null || typeof val === "undefined");
//         const is_changing_from_rashody = (frm.doc.party_type === "Расходы" && val !== "Расходы");
//         if (is_clearing || is_changing_from_rashody) {
//           console.warn("[guard] blocked party_type change during protection window:", val);
//           return Promise.resolve(); // hech nima qilmaymiz
//         }
//       }
//     }
//     return _orig_set_value(field, val);
//   };

//   frm._ext_set_value_patched = true;
// };

// // --- Awesomplete tanlovini darhol commit qilamiz
// ext_accounts.pe.bind_awesomplete_commit = function (frm) {
//   const fld = frm.fields_dict.party_type;
//   if (!fld || !fld.input || fld._ext_bound) return;
//   fld._ext_bound = true;

//   const commitValue = (raw) => {
//     const val = (raw && (raw.value || raw)) || fld.input.value || "";
//     if (!val) return;

//     // 1) Guard: 1 soniya davomida bo'shatish/ozgartirishni bloklash
//     frm._protect_party_type_until = Date.now() + 1000;

//     // 2) Commit
//     frm.set_value("party_type", val).then(() => {
//       // 3) UI toggling – keyingi tickda
//       setTimeout(() => {
//         ext_accounts.pe.toggle_fields(frm);
//       }, 0);
//     });
//   };

//   fld.input.addEventListener("awesomplete-selectcomplete", (e) => {
//     commitValue(e && e.text);
//   });
//   fld.input.addEventListener("keydown", (e) => {
//     if (e.key === "Enter") commitValue();
//   });
//   fld.input.addEventListener("blur", () => {
//     if (!frm.doc.party_type && fld.input.value) commitValue();
//   });
// };

// // --- Form events
// frappe.ui.form.on("Payment Entry", {
//   setup(frm) {
//     ext_accounts.pe.setup_queries(frm);
//     ext_accounts.pe.install_guard(frm);
//     ext_accounts.pe.bind_awesomplete_commit(frm);
//   },

//   onload(frm) {
//     if (!frm.doc.payment_type && frm.doc.__islocal) {
//       frm.set_value("payment_type", "Pay");
//     }
//     frm.doc.__last_payment_type = frm.doc.payment_type || "";
//     ext_accounts.pe.setup_queries(frm);
//     ext_accounts.pe.install_guard(frm);
//     ext_accounts.pe.bind_awesomplete_commit(frm);
//   },

//   refresh(frm) {
//     ext_accounts.pe.setup_queries(frm);
//     ext_accounts.pe.toggle_fields(frm);
//     ext_accounts.pe.install_guard(frm);
//     ext_accounts.pe.bind_awesomplete_commit(frm);
//   },

//   payment_type(frm) {
//     if (frm.doc.__last_payment_type !== frm.doc.payment_type) {
//       if (frm.doc.party_type) frm.set_value("party_type", "");
//       frm.doc.__last_payment_type = frm.doc.payment_type || "";
//     }
//     ext_accounts.pe.setup_queries(frm);
//     frm.refresh_field("party_type");
//   },

//   party_type(frm) {
//     // Agar foydalanuvchi boshqa tur tanlasa – guardni olib tashlaymiz
//     if (frm.doc.party_type !== "Расходы") {
//       frm._protect_party_type_until = 0;
//     }

//     setTimeout(() => {
//       if (frm.doc.party_type === "Расходы") {
//         if (frm.doc.references && frm.doc.references.length) {
//           frm.clear_table("references");
//           frm.refresh_field("references");
//         }
//         ext_accounts.pe.toggle_fields(frm);
//         frappe.show_alert({ message: __("Expense Account tanlang"), indicator: "blue" });
//       } else if (frm.doc.party_type) {
//         if (frm.doc.expense_account) frm.set_value("expense_account", null);
//         ext_accounts.pe.toggle_fields(frm);
//       }
//     }, 0);
//   },

//   expense_account(frm) {
//     if (frm.doc.party_type === "Расходы" && frm.doc.expense_account) {
//       frappe.db.get_value(
//         "Account",
//         frm.doc.expense_account,
//         ["account_currency", "account_name"],
//         function (r) {
//           if (r) {
//             const currency = r.account_currency || frm.doc.company_currency;
//             frappe.show_alert({
//               message: __("Account: {0}, Currency: {1}", [r.account_name, currency]),
//               indicator: "green",
//             });
//           }
//         }
//       );
//     }
//   },

//   validate(frm) {
//     if (frm.doc.party_type === "Расходы") {
//       if (!frm.doc.expense_account) {
//         frappe.throw(__("Expense Account majburiy"));
//       }
//       if (!frm.doc.paid_from && frm.doc.payment_type === "Pay") {
//         frappe.throw(__("Paid From account majburiy"));
//       }
//       if (!frm.doc.paid_amount || frm.doc.paid_amount <= 0) {
//         frappe.throw(__("Paid Amount 0 dan katta bo'lishi kerak"));
//       }
//     }
//   },
// });
