import frappe
from frappe.utils import flt


def execute(filters=None):
    if not filters:
        return [], []
    return get_columns(filters), get_data(filters)


def get_columns(filters):
    currency = filters.get("currency", "")

    base = [
        {"label": "Контрагент тури", "fieldname": "party_type", "fieldtype": "Data", "width": 130},
        {"label": "Контрагент", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 200},
        {"label": "Валюта", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": "Акт Сверка", "fieldname": "akt_sverka_link", "fieldtype": "Data", "width": 120},
    ]

    def money_cols(label_cur, suffix):
        tag = f" {label_cur}" if label_cur else ""
        return [
            {"label": f"Кредит{tag} (дан олдин)", "fieldname": f"opening_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Дебет{tag} (дан олдин)", "fieldname": f"opening_debit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Кредит{tag} (давр)", "fieldname": f"period_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Дебет{tag} (давр)", "fieldname": f"period_debit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Сўнгги Кредит{tag}", "fieldname": f"final_credit_{suffix}", "fieldtype": "Currency", "width": 150},
            {"label": f"Сўнгги Дебет{tag}", "fieldname": f"final_debit_{suffix}", "fieldtype": "Currency", "width": 150},
        ]

    if not currency:
        return base + money_cols("UZS", "uzs") + money_cols("USD", "usd")
    return base + money_cols("", currency.lower())


def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    party_type = filters.get("party_type")
    party = filters.get("party")
    currency_filter = filters.get("currency")

    opening = _aggregate_gl(party_type, party, to_date=from_date)
    period = _aggregate_gl(party_type, party, from_date=from_date, to_date=to_date)

    parties = sorted({k[:2] for k in (*opening, *period)})

    data = []
    totals = {}
    money_keys = (
        "opening_credit_uzs", "opening_debit_uzs", "opening_credit_usd", "opening_debit_usd",
        "period_credit_uzs", "period_debit_uzs", "period_credit_usd", "period_debit_usd",
        "final_credit_uzs", "final_debit_uzs", "final_credit_usd", "final_debit_usd",
    )

    for pt, p in parties:
        party_currency = _get_party_currency(pt, p)
        if currency_filter and party_currency != currency_filter:
            continue

        row = {"party_type": pt, "party": p, "currency": party_currency, "akt_sverka_link": "Акт Сверка"}

        for cur, suffix in (("UZS", "uzs"), ("USD", "usd")):
            o = opening.get((pt, p, cur), (0, 0))
            r = period.get((pt, p, cur), (0, 0))
            opening_net = o[0] - o[1]
            final_net = opening_net + r[0] - r[1]

            row[f"opening_credit_{suffix}"] = opening_net if opening_net > 0 else 0
            row[f"opening_debit_{suffix}"] = -opening_net if opening_net < 0 else 0
            row[f"period_credit_{suffix}"] = r[0]
            row[f"period_debit_{suffix}"] = r[1]
            row[f"final_credit_{suffix}"] = final_net if final_net > 0 else 0
            row[f"final_debit_{suffix}"] = -final_net if final_net < 0 else 0

        if not any(row[k] for k in money_keys):
            continue

        data.append(row)
        for k in money_keys:
            totals[k] = totals.get(k, 0) + row[k]

    if data:
        total_row = {"party_type": "", "party": "ЖАМИ", "currency": "", "akt_sverka_link": "", "is_total_row": True}
        total_row.update(totals)
        data.insert(0, total_row)

    return data


def _aggregate_gl(party_type=None, party=None, from_date=None, to_date=None):
    """Return {(party_type, party, currency): (credit, debit)} grouped from GL Entry."""
    conditions = ["party IS NOT NULL", "party != ''", "is_cancelled = 0", "account_currency IN ('UZS', 'USD')"]
    values = []

    if from_date and to_date:
        conditions.append("posting_date BETWEEN %s AND %s")
        values.extend([from_date, to_date])
    elif to_date:
        conditions.append("posting_date < %s")
        values.append(to_date)

    if party_type:
        conditions.append("party_type = %s")
        values.append(party_type)
    if party:
        conditions.append("party = %s")
        values.append(party)

    rows = frappe.db.sql(f"""
        SELECT party_type, party, account_currency AS currency,
               SUM(credit_in_account_currency) AS credit,
               SUM(debit_in_account_currency) AS debit
        FROM `tabGL Entry`
        WHERE {" AND ".join(conditions)}
        GROUP BY party_type, party, account_currency
    """, tuple(values), as_dict=True)

    return {(r.party_type, r.party, r.currency): (flt(r.credit), flt(r.debit)) for r in rows}


def _get_party_currency(party_type, party):
    return frappe.db.get_value(
        "Party Financial Defaults",
        {"party_type": party_type, "party": party},
        "currency",
    ) or "UZS"
