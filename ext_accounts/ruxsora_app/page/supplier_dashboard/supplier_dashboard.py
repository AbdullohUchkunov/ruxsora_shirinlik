from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from ext_accounts.ruxsora_app.dashboard_data import get_reporting_currency
from ext_accounts.ruxsora_app.dashboard_data import MONTH_LABELS


def _get_company_details() -> tuple[str, str]:
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or frappe.db.get_value("Company", {}, "name")
	)
	if not company:
		return "Компания", get_reporting_currency()

	return company, get_reporting_currency()


def _get_reference_date():
	purchase_row = frappe.db.sql(
		"""
		SELECT MAX(posting_date) AS posting_date
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
		  AND COALESCE(is_return, 0) = 0
		""",
		as_dict=True,
	)[0]
	payment_row = frappe.db.sql(
		"""
		SELECT MAX(posting_date) AS posting_date
		FROM `tabPayment Entry`
		WHERE docstatus = 1
		  AND payment_type = 'Pay'
		  AND party_type = 'Supplier'
		""",
		as_dict=True,
	)[0]

	dates = [value for value in (purchase_row.posting_date, payment_row.posting_date) if value]
	if not dates:
		return getdate(today())

	return max(getdate(value) for value in dates)


def _get_years() -> list[str]:
	rows = frappe.db.sql(
		"""
		SELECT year_value
		FROM (
			SELECT DISTINCT YEAR(posting_date) AS year_value
			FROM `tabPurchase Invoice`
			WHERE docstatus = 1
			  AND COALESCE(is_return, 0) = 0
			  AND posting_date IS NOT NULL
			UNION
			SELECT DISTINCT YEAR(posting_date) AS year_value
			FROM `tabPayment Entry`
			WHERE docstatus = 1
			  AND payment_type = 'Pay'
			  AND party_type = 'Supplier'
			  AND posting_date IS NOT NULL
		) years
		WHERE year_value IS NOT NULL
		ORDER BY year_value
		""",
		as_dict=True,
	)
	values = [str(row.year_value) for row in rows if row.year_value]
	if values:
		return values
	return [str(getdate(today()).year)]


def _get_default_period() -> tuple[str, str]:
	reference_date = _get_reference_date()
	return str(reference_date.year), MONTH_LABELS[reference_date.month - 1]


def _normalize_filters(year: str | None, month: str | None) -> tuple[str, str | None]:
	years = _get_years()
	default_year, default_month = _get_default_period()
	selected_year = str(year) if str(year) in years else default_year
	selected_month = month if month in MONTH_LABELS else default_month
	return selected_year, selected_month


def _get_period_range(year: str, month: str | None) -> tuple[str, str, str]:
	if month in MONTH_LABELS:
		month_index = MONTH_LABELS.index(month) + 1
		reference_date = getdate(f"{year}-{month_index:02d}-01")
		return str(get_first_day(reference_date)), str(get_last_day(reference_date)), f"{month} {year}"

	return f"{year}-01-01", f"{year}-12-31", year


def _party_dashboard_config(view: str) -> dict[str, str]:
	if view == "client":
		return {
			"party_type": "Customer",
			"party_field": "customer",
			"payment_party_field": "party",
			"name_field": "customer_name",
			"party_title": "Клиент",
			"party_title_plural": "Клиенты",
			"invoice_label": "Продажа",
			"invoice_table": "tabSales Invoice",
			"invoice_item_table": "tabSales Invoice Item",
			"payment_amount_field": "received_amount",
			"payment_currency_field": "paid_to_account_currency",
			"payment_account_field": "paid_to",
			"payment_type": "Receive",
			"payment_party_table": "tabCustomer",
			"payment_party_name_field": "customer_name",
			"unknown_party": "Неизвестный клиент",
		}

	return {
		"party_type": "Supplier",
		"party_field": "supplier",
		"payment_party_field": "party",
		"name_field": "supplier_name",
		"party_title": "Поставщик",
		"party_title_plural": "Поставщики",
		"invoice_label": "Приход",
		"invoice_table": "tabPurchase Invoice",
		"invoice_item_table": "tabPurchase Invoice Item",
		"payment_amount_field": "paid_amount",
		"payment_currency_field": "paid_from_account_currency",
		"payment_account_field": "paid_from",
		"payment_type": "Pay",
		"payment_party_table": "tabSupplier",
		"payment_party_name_field": "supplier_name",
		"unknown_party": "Неизвестный поставщик",
	}


def _party_filter_clause(view: str, party: str | None, params: dict[str, Any], alias: str) -> str:
	if not party:
		return ""
	config = _party_dashboard_config(view)
	params["party"] = party
	field = config["payment_party_field"] if alias in {"pe", "ple"} else config["party_field"]
	return f" AND {alias}.{field} = %(party)s"


def _get_party_invoice_rows(view: str, start_date: str, end_date: str, party: str | None = None) -> list[dict[str, Any]]:
	config = _party_dashboard_config(view)
	params = {"start_date": start_date, "end_date": end_date}
	party_clause = _party_filter_clause(view, party, params, "doc")

	return frappe.db.sql(
		f"""
		SELECT
			invoice.party,
			invoice.party_name,
			invoice.posting_date,
			invoice.currency,
			invoice.company,
			SUM(CASE WHEN invoice.posting_date < %(start_date)s THEN invoice.grand_total ELSE 0 END) AS opening_amount,
			SUM(CASE WHEN invoice.posting_date BETWEEN %(start_date)s AND %(end_date)s THEN invoice.grand_total ELSE 0 END) AS inflow_amount,
			SUM(CASE WHEN invoice.posting_date < %(start_date)s THEN invoice.qty_total ELSE 0 END) AS opening_kg,
			SUM(CASE WHEN invoice.posting_date BETWEEN %(start_date)s AND %(end_date)s THEN invoice.qty_total ELSE 0 END) AS inflow_kg
		FROM (
			SELECT
				doc.name,
				doc.{config['party_field']} AS party,
				COALESCE(NULLIF(doc.{config['name_field']}, ''), doc.{config['party_field']}, '{config['party_title_plural']}') AS party_name,
				doc.posting_date,
				doc.currency,
				doc.company,
				COALESCE(doc.grand_total, 0) AS grand_total,
				SUM(COALESCE(item.stock_qty, item.qty, 0)) AS qty_total
			FROM `{config['invoice_table']}` doc
			LEFT JOIN `{config['invoice_item_table']}` item ON item.parent = doc.name
			WHERE doc.docstatus = 1
			  {party_clause}
			GROUP BY doc.name, doc.{config['party_field']}, party_name, doc.posting_date, doc.currency, doc.company, doc.grand_total
		) invoice
		GROUP BY invoice.party, invoice.party_name, invoice.posting_date, invoice.currency, invoice.company
		""",
		params,
		as_dict=True,
	)


def _get_party_journal_rows(view: str, start_date: str, end_date: str, party: str | None = None) -> list[dict[str, Any]]:
	config = _party_dashboard_config(view)
	params = {"start_date": start_date, "end_date": end_date}
	party_clause = _party_filter_clause(view, party, params, "ple")

	return frappe.db.sql(
		f"""
		SELECT
			ple.party,
			COALESCE(NULLIF(party.{config['payment_party_name_field']}, ''), ple.party, '{config['unknown_party']}') AS party_name,
			ple.posting_date,
			ple.company,
			ple.account_currency AS currency,
			SUM(CASE WHEN ple.posting_date < %(start_date)s THEN COALESCE(ple.amount_in_account_currency, 0) ELSE 0 END) AS opening_amount,
			SUM(CASE WHEN ple.posting_date BETWEEN %(start_date)s AND %(end_date)s THEN COALESCE(ple.amount_in_account_currency, 0) ELSE 0 END) AS period_amount
		FROM `tabPayment Ledger Entry` ple
		LEFT JOIN `{config['payment_party_table']}` party ON party.name = ple.party
		WHERE ple.docstatus = 1
		  AND COALESCE(ple.delinked, 0) = 0
		  AND ple.party_type = %(party_type)s
		  AND ple.party IS NOT NULL
		  AND ple.voucher_type = 'Journal Entry'
		  {party_clause}
		GROUP BY ple.party, party_name, ple.posting_date, ple.company, ple.account_currency
		""",
		{**params, "party_type": config["party_type"]},
		as_dict=True,
	)


def _get_party_payment_rows(view: str, start_date: str, end_date: str, party: str | None = None) -> list[dict[str, Any]]:
	config = _party_dashboard_config(view)
	params = {"start_date": start_date, "end_date": end_date}
	party_clause = _party_filter_clause(view, party, params, "pe")

	return frappe.db.sql(
		f"""
		SELECT
			pe.party AS party,
			COALESCE(NULLIF(party.{config['payment_party_name_field']}, ''), pe.party, '{config['unknown_party']}') AS party_name,
			pe.posting_date,
			pe.{config['payment_currency_field']} AS currency,
			pe.company,
			SUM(CASE WHEN pe.posting_date < %(start_date)s AND acc.account_type = 'Cash'
				THEN COALESCE(pe.{config['payment_amount_field']}, 0) ELSE 0 END) AS opening_cash_amount,
			SUM(CASE WHEN pe.posting_date < %(start_date)s AND acc.account_type = 'Bank'
				THEN COALESCE(pe.{config['payment_amount_field']}, 0) ELSE 0 END) AS opening_bank_amount,
			SUM(CASE WHEN pe.posting_date BETWEEN %(start_date)s AND %(end_date)s AND acc.account_type = 'Cash'
				THEN COALESCE(pe.{config['payment_amount_field']}, 0) ELSE 0 END) AS cash_payment_amount,
			SUM(CASE WHEN pe.posting_date BETWEEN %(start_date)s AND %(end_date)s AND acc.account_type = 'Bank'
				THEN COALESCE(pe.{config['payment_amount_field']}, 0) ELSE 0 END) AS bank_payment_amount
		FROM `tabPayment Entry` pe
		LEFT JOIN `{config['payment_party_table']}` party ON party.name = pe.party
		LEFT JOIN `tabAccount` acc ON acc.name = pe.{config['payment_account_field']}
		WHERE pe.docstatus = 1
		  AND pe.payment_type = %(payment_type)s
		  AND pe.party_type = %(party_type)s
		  AND pe.party IS NOT NULL
		  {party_clause}
		GROUP BY pe.party, party_name, pe.posting_date, pe.{config['payment_currency_field']}, pe.company
		""",
		{
			**params,
			"party_type": config["party_type"],
			"payment_type": config["payment_type"],
		},
		as_dict=True,
	)


def _new_party_entry(party: str | None, party_name: str | None, currency: str) -> dict[str, Any]:
	return {
		"party": party,
		"party_name": party_name or party,
		"currency": currency,
		"opening": 0.0,
		"inflow": 0.0,
		"kg": 0.0,
		"cash_payment": 0.0,
		"bank_payment": 0.0,
		"opening_base": 0.0,
		"inflow_base": 0.0,
		"cash_payment_base": 0.0,
		"bank_payment_base": 0.0,
		"balance_base": 0.0,
	}


def _party_currency_key(party: str | None, currency: str | None) -> str:
	return f"{party or ''}::{currency or get_reporting_currency()}"


def _get_party_gl_balances(view: str, to_date: str, party: str | None = None, before_date: bool = False) -> dict[str, dict[str, Any]]:
	config = _party_dashboard_config(view)
	params: dict[str, Any] = {
		"party_type": config["party_type"],
		"date": to_date,
	}
	party_clause = ""
	if party:
		party_clause = " AND gle.party = %(party)s"
		params["party"] = party
	date_operator = "<" if before_date else "<="

	rows = frappe.db.sql(
		f"""
		SELECT
			gle.party,
			COALESCE(NULLIF(party.{config['payment_party_name_field']}, ''), gle.party, '{config['unknown_party']}') AS party_name,
			gle.account_currency AS currency,
			SUM(COALESCE(gle.debit_in_account_currency, 0) - COALESCE(gle.credit_in_account_currency, 0)) AS debit_minus_credit
		FROM `tabGL Entry` gle
		LEFT JOIN `{config['payment_party_table']}` party ON party.name = gle.party
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.party_type = %(party_type)s
		  AND gle.party IS NOT NULL
		  AND gle.party != ''
		  AND gle.posting_date {date_operator} %(date)s
		  {party_clause}
		GROUP BY gle.party, party_name, gle.account_currency
		""",
		params,
		as_dict=True,
	)

	balances: dict[str, dict[str, Any]] = {}
	sign = 1 if view == "client" else -1
	for row in rows:
		key = _party_currency_key(row.party, row.currency)
		entry = balances.setdefault(
			key,
			{"party": row.party, "party_name": row.party_name, "currency": row.currency, "balance": 0.0},
		)
		entry["party_name"] = row.party_name
		entry["currency"] = row.currency
		entry["balance"] += sign * flt(row.debit_minus_credit)

	return balances


def _build_party_rows(view: str, start_date: str, end_date: str, party: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	rows_by_key: dict[str, dict[str, Any]] = {}
	totals = {
		"opening": 0.0,
		"inflow": 0.0,
		"cash_payment": 0.0,
		"bank_payment": 0.0,
		"sum_balance": 0.0,
		"sum_prepayment": 0.0,
		"sum_debt": 0.0,
		"kg": 0.0,
	}
	totals_by_currency: dict[str, dict[str, float]] = {}

	opening_balances = _get_party_gl_balances(view, start_date, party=party, before_date=True)
	closing_balances = _get_party_gl_balances(view, end_date, party=party)

	for key, row in {**opening_balances, **closing_balances}.items():
		entry = rows_by_key.setdefault(
			key,
			_new_party_entry(row.get("party"), row.get("party_name"), row.get("currency") or get_reporting_currency()),
		)
		entry["party_name"] = row.get("party_name") or entry["party_name"]
		entry["currency"] = row.get("currency") or entry["currency"]
		entry["opening_base"] = flt(opening_balances.get(key, {}).get("balance"))
		entry["opening"] = entry["opening_base"]
		entry["balance_base"] = flt(closing_balances.get(key, {}).get("balance"))

	for row in _get_party_invoice_rows(view, start_date, end_date, party=party):
		key = _party_currency_key(row.party, row.currency)
		entry = rows_by_key.setdefault(
			key,
			_new_party_entry(row.party, row.party_name, row.currency),
		)
		entry["party_name"] = row.party_name
		entry["currency"] = row.currency or entry["currency"]
		entry["kg"] += flt(row.inflow_kg)
		inflow_base = flt(row.inflow_amount)
		entry["inflow"] += inflow_base
		entry["inflow_base"] += inflow_base

	for row in _get_party_journal_rows(view, start_date, end_date, party=party):
		key = _party_currency_key(row.party, row.currency)
		entry = rows_by_key.setdefault(
			key,
			_new_party_entry(row.party, row.party_name, row.currency),
		)
		entry["party_name"] = row.party_name
		entry["currency"] = row.currency or entry["currency"]
		inflow_base = flt(row.period_amount)
		entry["inflow"] += inflow_base
		entry["inflow_base"] += inflow_base

	for row in _get_party_payment_rows(view, start_date, end_date, party=party):
		key = _party_currency_key(row.party, row.currency)
		entry = rows_by_key.setdefault(
			key,
			_new_party_entry(row.party, row.party_name, row.currency),
		)
		entry["party_name"] = row.party_name
		entry["currency"] = row.currency or entry["currency"]
		period_cash = flt(row.cash_payment_amount)
		period_bank = flt(row.bank_payment_amount)

		entry["cash_payment"] += period_cash
		entry["bank_payment"] += period_bank
		entry["cash_payment_base"] += period_cash
		entry["bank_payment_base"] += period_bank

	rows = []
	for value in rows_by_key.values():
		balance_base = value["balance_base"]

		if not any(
			flt(number)
			for number in (
				value["opening"],
				value["inflow"],
				value["cash_payment"],
				value["bank_payment"],
				value["kg"],
				balance_base,
			)
		):
			continue

		totals["opening"] += value["opening_base"]
		totals["inflow"] += value["inflow_base"]
		totals["cash_payment"] += value["cash_payment_base"]
		totals["bank_payment"] += value["bank_payment_base"]
		totals["sum_balance"] += balance_base
		totals["kg"] += value["kg"]
		currency_totals = totals_by_currency.setdefault(
			value["currency"] or get_reporting_currency(),
			{"sum_prepayment": 0.0, "sum_debt": 0.0},
		)

		if balance_base < 0:
			totals["sum_prepayment"] += abs(balance_base)
			currency_totals["sum_prepayment"] += abs(balance_base)
		else:
			totals["sum_debt"] += balance_base
			currency_totals["sum_debt"] += balance_base

		rows.append(
			{
				"party": value["party"],
				"party_name": value["party_name"],
				"currency": value["currency"] or get_reporting_currency(),
				"opening": round(value["opening"], 2),
				"inflow": round(value["inflow"], 2),
				"kg": round(value["kg"], 2),
				"cash_payment": round(value["cash_payment"], 2),
				"bank_payment": round(value["bank_payment"], 2),
				"sum_balance": round(balance_base, 2),
			}
		)

	rows.sort(key=lambda row: (row["sum_balance"] >= 0, row["sum_balance"], row["party_name"]))

	rounded_totals = {key: round(value, 2) for key, value in totals.items()}
	rounded_totals["by_currency"] = [
		{
			"currency": currency,
			"sum_prepayment": round(values["sum_prepayment"], 2),
			"sum_debt": round(values["sum_debt"], 2),
		}
		for currency, values in sorted(totals_by_currency.items())
	]
	return rows, rounded_totals


@frappe.whitelist()
def get_dashboard_context(year: str | None = None, month: str | None = None, view: str | None = None, party: str | None = None):
	company_name, company_currency = _get_company_details()
	selected_year, selected_month = _normalize_filters(year, month)
	start_date, end_date, period_label = _get_period_range(selected_year, selected_month)
	selected_view = view if view in {"client", "supplier"} else "supplier"
	config = _party_dashboard_config(selected_view)
	rows, totals = _build_party_rows(selected_view, start_date, end_date, party=party)
	selected_party_name = next((row["party_name"] for row in rows if row["party"] == party), None) if party else None

	return {
		"company_name": company_name,
		"company_currency": company_currency,
		"period_label": period_label,
		"years": _get_years(),
		"months": MONTH_LABELS,
		"view": selected_view,
		"view_label": config["party_title_plural"],
		"default_filters": {
			"year": selected_year,
			"month": selected_month,
			"view": selected_view,
			"party": party,
		},
		"selected_party_name": selected_party_name,
		"columns": {
			"party_label": config["party_title"],
			"inflow_label": config["invoice_label"],
			"currency_label": "Валюта",
			"kg_label": "KG",
			"cash_payment_label": "Оплата наличными",
			"bank_payment_label": "Оплата банком",
			"balance_label": "Сум остаток",
		},
		"kpis": {
			"sum_prepayment": totals["sum_prepayment"],
			"sum_debt": totals["sum_debt"],
			"by_currency": totals.get("by_currency", []),
		},
		"rows": rows,
		"totals": totals,
	}
