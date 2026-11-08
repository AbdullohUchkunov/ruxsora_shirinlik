// Copyright (c) 2025, abdulloh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Kassa", {
    onload: function(frm) {
        // Kompaniya maydoni yashirin - yangi hujjatga default kompaniyani qo'yish
        if (frm.is_new() && !frm.doc.company) {
            let company = frappe.defaults.get_user_default("Company")
                || frappe.defaults.get_global_default("company");
            if (company) {
                frm.doc.company = company;
            }
        }
    },

    refresh: function(frm) {
        // Счет расходов: faqat Indirect Expenses ichidagi hisoblar
        frm.set_query("expense_account", function() {
            return {
                query: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_expense_accounts",
                filters: {
                    company: frm.doc.company
                }
            };
        });

        // Set mode_of_payment query based on transaction type
        frm.trigger("set_mode_of_payment_query");

        // Set mode_of_payment_to query based on transaction type and mode_of_payment
        frm.trigger("set_mode_of_payment_to_query");

        // Submit/cancel qilingan hujjatda hech narsani o'zgartirmaymiz,
        // aks holda forma "Not Saved" bo'lib, Update tugmasi chiqadi
        if (frm.doc.docstatus === 0) {
            if (frm.doc.mode_of_payment && frm.doc.company) {
                frm.trigger("update_balance");
            }
            if (frm.doc.mode_of_payment_to && frm.doc.company) {
                frm.trigger("update_balance_to");
            }
            if (frm.doc.transaction_type === "Конвертация" && !frm.doc.exchange_rate) {
                frm.trigger("fetch_exchange_rate");
            }
        }

        // Update balance label based on transaction type
        frm.trigger("update_balance_label");
    },

    company: function(frm) {
        // Clear fields when company changes
        frm.set_value("mode_of_payment", "");
        frm.set_value("cash_account", "");
        frm.set_value("balance", 0);
        frm.set_value("party", "");
        frm.set_value("expense_account", "");
    },

    mode_of_payment: function(frm) {
        if (frm.doc.mode_of_payment && frm.doc.company) {
            // Get cash account and currency for this mode of payment
            frappe.call({
                method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_cash_account_with_currency",
                args: {
                    mode_of_payment: frm.doc.mode_of_payment,
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message && r.message.account) {
                        frm.set_value("cash_account", r.message.account);
                        frm.set_value("cash_account_currency", r.message.currency);
                        frm.trigger("update_balance");
                        frm.trigger("validate_currency");
                    } else {
                        frappe.msgprint(__("Для данного способа оплаты не настроен счет кассы для компании {0}", [frm.doc.company]));
                        frm.set_value("cash_account", "");
                        frm.set_value("cash_account_currency", "");
                        frm.set_value("balance", 0);
                    }
                }
            });
        } else {
            frm.set_value("cash_account", "");
            frm.set_value("cash_account_currency", "");
            frm.set_value("balance", 0);
        }

        // Clear and update mode_of_payment_to when mode_of_payment changes
        if (in_list(["Перемещения", "Конвертация"], frm.doc.transaction_type)) {
            frm.set_value("mode_of_payment_to", "");
            frm.set_value("cash_account_to", "");
            frm.set_value("balance_to", 0);
            frm.trigger("set_mode_of_payment_to_query");
        }
    },

    update_balance: function(frm) {
        if (frm.doc.cash_account && frm.doc.company) {
            frappe.call({
                method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_account_balance",
                args: {
                    account: frm.doc.cash_account,
                    company: frm.doc.company
                },
                callback: function(r) {
                    set_silently(frm, "balance", r.message || 0);
                }
            });
        }
    },

    transaction_type: function(frm) {
        // Clear party fields when transaction type changes
        frm.set_value("party_type", "");
        frm.set_value("party", "");
        frm.set_value("expense_account", "");
        frm.set_value("party_name", "");
        frm.set_value("expense_account_name", "");

        // Clear payment and transfer/conversion fields
        frm.set_value("mode_of_payment", "");
        frm.set_value("cash_account", "");
        frm.set_value("balance", 0);
        frm.set_value("mode_of_payment_to", "");
        frm.set_value("cash_account_to", "");
        frm.set_value("balance_to", 0);
        frm.set_value("exchange_rate", 0);
        frm.set_value("debit_amount", 0);
        frm.set_value("credit_amount", 0);
        frm.set_value("party_currency", "");
        frm.set_value("party_exchange_rate", 0);
        frm.set_value("party_amount", 0);

        // Set mode_of_payment and mode_of_payment_to queries
        frm.trigger("set_mode_of_payment_query");
        frm.trigger("set_mode_of_payment_to_query");

        // Fetch exchange rate for conversion
        if (frm.doc.transaction_type === "Конвертация") {
            frm.trigger("fetch_exchange_rate");
        }

        // Update balance label
        frm.trigger("update_balance_label");
    },

    mode_of_payment_to: function(frm) {
        if (frm.doc.mode_of_payment_to && frm.doc.company) {
            // Get cash account for this mode of payment
            frappe.call({
                method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_cash_account_with_currency",
                args: {
                    mode_of_payment: frm.doc.mode_of_payment_to,
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message && r.message.account) {
                        frm.set_value("cash_account_to", r.message.account);
                        frm.set_value("cash_account_to_currency", r.message.currency);
                        frm.trigger("update_balance_to");
                    } else {
                        frappe.msgprint(__("Для данного способа оплаты не настроен счет кассы для компании {0}", [frm.doc.company]));
                        frm.set_value("cash_account_to", "");
                        frm.set_value("cash_account_to_currency", "");
                        frm.set_value("balance_to", 0);
                    }
                }
            });
        } else {
            frm.set_value("cash_account_to", "");
            frm.set_value("cash_account_to_currency", "");
            frm.set_value("balance_to", 0);
        }
    },

    update_balance_to: function(frm) {
        if (frm.doc.cash_account_to && frm.doc.company) {
            frappe.call({
                method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_account_balance",
                args: {
                    account: frm.doc.cash_account_to,
                    company: frm.doc.company
                },
                callback: function(r) {
                    set_silently(frm, "balance_to", r.message || 0);
                }
            });
        }
    },

    set_mode_of_payment_query: function(frm) {
        frm.set_query("mode_of_payment", function() {
            let filters = {};

            if (frm.doc.transaction_type === "Перемещения") {
                // For transfer: only Cash UZS and Bank (No ref), no Cash USD
                filters.name = ["in", ["Cash UZS", "Bank (No ref)"]];
            }

            return { filters: filters };
        });
    },

    set_mode_of_payment_to_query: function(frm) {
        frm.set_query("mode_of_payment_to", function() {
            let filters = {};

            if (frm.doc.transaction_type === "Перемещения") {
                // For transfer: only between Cash UZS and Bank (No ref)
                // No Cash USD for Перемещения
                if (frm.doc.mode_of_payment === "Cash UZS") {
                    filters.name = "Bank (No ref)";
                } else if (frm.doc.mode_of_payment === "Bank (No ref)") {
                    filters.name = "Cash UZS";
                }
            } else if (frm.doc.transaction_type === "Конвертация") {
                // For conversion: Cash USD <-> Cash UZS or Bank (No ref)
                if (frm.doc.mode_of_payment === "Cash USD") {
                    filters.name = ["in", ["Cash UZS", "Bank (No ref)"]];
                } else if (frm.doc.mode_of_payment === "Cash UZS" || frm.doc.mode_of_payment === "Bank (No ref)") {
                    filters.name = "Cash USD";
                }
            }

            return { filters: filters };
        });
    },

    fetch_exchange_rate: function(frm) {
        // Fetch today's exchange rate from Currency Exchange
        frappe.call({
            method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_exchange_rate",
            args: {
                from_currency: "USD",
                to_currency: "UZS",
                date: frm.doc.date || frappe.datetime.get_today()
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value("exchange_rate", r.message);
                }
            }
        });
    },

    debit_amount: function(frm) {
        // Calculate credit_amount when debit_amount changes (for conversion)
        frm.trigger("calculate_conversion_amount");
    },

    exchange_rate: function(frm) {
        // Calculate credit_amount when exchange_rate changes (for conversion)
        frm.trigger("calculate_conversion_amount");
    },

    calculate_conversion_amount: function(frm) {
        if (frm.doc.transaction_type !== "Конвертация") return;
        if (!frm.doc.debit_amount || !frm.doc.exchange_rate) return;

        // Determine direction: UZS -> USD or USD -> UZS
        // If mode_of_payment is Cash UZS or Bank (No ref), we're converting FROM UZS TO USD
        // debit_amount is in UZS, credit_amount should be in USD
        if (in_list(["Cash UZS", "Bank (No ref)"], frm.doc.mode_of_payment)) {
            // UZS -> USD: credit_amount = debit_amount / exchange_rate
            let credit = flt(frm.doc.debit_amount) / flt(frm.doc.exchange_rate);
            frm.set_value("credit_amount", flt(credit, 2));
        } else if (frm.doc.mode_of_payment === "Cash USD") {
            // USD -> UZS: credit_amount = debit_amount * exchange_rate
            let credit = flt(frm.doc.debit_amount) * flt(frm.doc.exchange_rate);
            frm.set_value("credit_amount", flt(credit, 0));
        }
    },

    update_balance_label: function(frm) {
        // Update balance label based on transaction type
        if (in_list(["Перемещения", "Конвертация"], frm.doc.transaction_type)) {
            frm.set_df_property("balance", "label", "Остаток (откуда)");
        } else {
            frm.set_df_property("balance", "label", "Остаток");
        }
        frm.refresh_field("balance");
    },

    party_type: function(frm) {
        // Clear party and expense account when party type changes
        frm.set_value("party", "");
        frm.set_value("expense_account", "");
        frm.set_value("party_name", "");
        frm.set_value("expense_account_name", "");
        frm.set_value("party_currency", "");
        frm.set_value("party_amount", 0);

        // Set mandatory based on party type
        if (frm.doc.party_type === "Расходы") {
            frm.set_df_property("expense_account", "reqd", 1);
            frm.set_df_property("party", "reqd", 0);
        } else if (frm.doc.party_type === "Дивиденд") {
            frm.set_df_property("expense_account", "reqd", 0);
            frm.set_df_property("party", "reqd", 0);
        } else if (frm.doc.party_type) {
            frm.set_df_property("expense_account", "reqd", 0);
            frm.set_df_property("party", "reqd", 1);
        } else {
            frm.set_df_property("expense_account", "reqd", 0);
            frm.set_df_property("party", "reqd", 0);
        }

        frm.refresh_fields();
    },

    party: function(frm) {
        // Fetch party name and currency based on party type
        if (frm.doc.party && frm.doc.party_type) {
            let name_field = get_party_name_field(frm.doc.party_type);
            if (name_field) {
                frappe.db.get_value(frm.doc.party_type, frm.doc.party, name_field, function(r) {
                    if (r && r[name_field]) {
                        frm.set_value("party_name", r[name_field]);
                    }
                });
            }

            // Get party default currency for Customer/Supplier
            if (in_list(["Customer", "Supplier"], frm.doc.party_type)) {
                frappe.call({
                    method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_party_currency",
                    args: {
                        party_type: frm.doc.party_type,
                        party: frm.doc.party,
                        company: frm.doc.company
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value("party_currency", r.message);
                            frm.trigger("validate_currency");
                        }
                    }
                });
            }
        } else {
            frm.set_value("party_name", "");
            frm.set_value("party_currency", "");
            frm.set_value("party_amount", 0);
        }
    },

    validate_currency: function(frm) {
        // Kassa va kontragent valyutasi har xil bo'lsa (UZS kassa -> USD qarzdorlik),
        // kursni olib kelib, kontragent valyutasidagi summani hisoblaymiz
        if (is_cross_currency(frm)) {
            if (!flt(frm.doc.party_exchange_rate)) {
                frappe.call({
                    method: "ext_accounts.ruxsora_app.doctype.kassa.kassa.get_exchange_rate",
                    args: {
                        from_currency: "USD",
                        to_currency: "UZS",
                        date: frm.doc.date || frappe.datetime.get_today()
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value("party_exchange_rate", r.message);
                        }
                        frm.trigger("calculate_party_amount");
                    }
                });
            } else {
                frm.trigger("calculate_party_amount");
            }
        } else {
            frm.set_value("party_amount", 0);
        }
    },

    amount: function(frm) {
        frm.trigger("calculate_party_amount");
    },

    party_exchange_rate: function(frm) {
        frm.trigger("calculate_party_amount");
    },

    calculate_party_amount: function(frm) {
        if (!is_cross_currency(frm) || !flt(frm.doc.party_exchange_rate)) {
            frm.set_value("party_amount", 0);
            return;
        }

        let rate = flt(frm.doc.party_exchange_rate);
        let party_amount = 0;
        if (frm.doc.cash_account_currency === "UZS") {
            // UZS -> USD (serverdagi hisob bilan bir xil yaxlitlash)
            party_amount = flt(flt(frm.doc.amount) * flt(1 / rate, 9), 2);
        } else {
            // USD -> UZS
            party_amount = flt(flt(frm.doc.amount) * rate, 2);
        }
        frm.set_value("party_amount", party_amount);
    }
});

// Faqat ko'rsatish uchun qiymat qo'yish: formani "o'zgargan" (dirty) qilmaydi
function set_silently(frm, fieldname, value) {
    frm.doc[fieldname] = value;
    frm.refresh_field(fieldname);
}

function is_cross_currency(frm) {
    return in_list(["Приход", "Расход"], frm.doc.transaction_type)
        && in_list(["Customer", "Supplier"], frm.doc.party_type)
        && frm.doc.cash_account_currency
        && frm.doc.party_currency
        && frm.doc.cash_account_currency !== frm.doc.party_currency;
}

function get_party_name_field(party_type) {
    const name_fields = {
        "Customer": "customer_name",
        "Supplier": "supplier_name",
        "Shareholder": "title",
        "Employee": "employee_name"
    };
    return name_fields[party_type] || null;
}
