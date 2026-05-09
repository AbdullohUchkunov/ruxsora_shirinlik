from __future__ import annotations

import calendar
from typing import Any

import frappe
from frappe.utils import flt, getdate, today

from ext_accounts.ruxsora_app.dashboard_data import (
	MONTH_LABELS,
	convert_company_currency_amount_like_report,
	get_item_cogs_map,
	get_item_rcp_map,
)


MONTHS = [{"key": label.lower(), "label": label} for label in MONTH_LABELS]
MONTH_MAP = {item["key"]: index + 1 for index, item in enumerate(MONTHS)}


def _get_years() -> list[str]:
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT YEAR(posting_date) AS year
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND COALESCE(is_return, 0) = 0
		  AND posting_date IS NOT NULL
		ORDER BY year
		""",
		as_dict=True,
	)

	years = [str(row.year) for row in rows if row.year]
	if years:
		return years

	return [str(getdate(today()).year)]


def _get_default_period() -> tuple[str, str]:
	latest_row = frappe.db.sql(
		"""
		SELECT MAX(posting_date) AS posting_date
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND COALESCE(is_return, 0) = 0
		""",
		as_dict=True,
	)[0]

	reference_date = getdate(latest_row.posting_date) if latest_row.posting_date else getdate(today())
	return str(reference_date.year), MONTH_LABELS[reference_date.month - 1].lower()


def _normalize_filters(year: str | None, month: str | None) -> tuple[str, str]:
	years = _get_years()
	default_year, default_month = _get_default_period()
	selected_year = year if year in years else default_year
	selected_month = month if month in MONTH_MAP else default_month
	return selected_year, selected_month


def _get_product_rows(year: str, month: str) -> list[dict[str, Any]]:
	month_no = MONTH_MAP[month]
	report_end_date = getdate(f"{year}-{month_no:02d}-{calendar.monthrange(int(year), month_no)[1]:02d}")
	cogs_map = get_item_cogs_map(year, month_no)
	rcp_map = get_item_rcp_map(year, month_no)
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар') AS item_key,
			COALESCE(NULLIF(sii.item_name, ''), sii.item_code, 'Неизвестный товар') AS item,
			si.company,
			SUM(CASE WHEN COALESCE(si.is_return, 0) = 0 THEN COALESCE(sii.stock_qty, sii.qty, 0) ELSE 0 END) AS kg,
			SUM(COALESCE(sii.base_net_amount, 0)) AS sales,
			SUM(CASE WHEN COALESCE(si.is_return, 0) = 0 THEN COALESCE(sii.stock_qty, sii.qty, 0) * COALESCE(sii.incoming_rate, 0) ELSE 0 END) AS cost,
			0 AS rsp
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND YEAR(si.posting_date) = %(year)s
		  AND MONTH(si.posting_date) = %(month)s
		GROUP BY
			COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар'),
			COALESCE(NULLIF(sii.item_name, ''), sii.item_code, 'Неизвестный товар'),
			si.company
		ORDER BY sales DESC, item ASC
		""",
		{"year": int(year), "month": int(month_no)},
		as_dict=True,
	)

	grouped: dict[str, dict[str, Any]] = {}
	for row in rows:
		sales = convert_company_currency_amount_like_report(row.sales, report_end_date, row.company)
		cost = convert_company_currency_amount_like_report(row.cost, report_end_date, row.company)
		existing = grouped.setdefault(
			row.item_key,
			{
				"item_key": row.item_key,
				"item": row.item,
				"kg": 0.0,
				"sales": 0.0,
				"cost": 0.0,
			},
		)
		existing["kg"] += flt(row.kg)
		existing["sales"] += sales
		existing["cost"] += cost

	result = []
	for row in sorted(grouped.values(), key=lambda value: flt(value["sales"]), reverse=True):
		sales = flt(row["sales"])
		cost = flt(cogs_map.get(row["item_key"], row["cost"]))
		margin = sales - cost
		rsp = flt(rcp_map.get(row["item_key"]))
		profit = margin - rsp
		result.append(
			{
				"item": row["item"],
				"kg": round(flt(row["kg"])),
				"sales": round(sales),
				"cost": round(cost),
				"margin": round(margin),
				"rsp": round(rsp),
				"margin_percent": (margin / sales * 100) if sales else 0,
				"profit": round(profit),
			}
		)

	return result


@frappe.whitelist()
def get_dashboard_context(year: str | None = None, month: str | None = None):
	selected_year, selected_month = _normalize_filters(year, month)

	return {
		"default_filters": {
			"year": selected_year,
			"month": selected_month,
		},
		"years": _get_years(),
		"months": MONTHS,
		"presentation_currency": "USD",
		"product_rows": _get_product_rows(selected_year, selected_month),
	}
