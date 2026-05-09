from __future__ import annotations

from functools import lru_cache
import math
from typing import Any

import frappe
from frappe.utils import cint, flt, get_last_day, getdate, today

from ext_accounts.ruxsora_app.dashboard_data import (
    convert_company_currency_amount,
    convert_to_reporting_currency,
    format_number,
    get_cash_total,
    get_cogs_total,
    get_creditor_total,
    get_debtor_balance_rows,
    get_debtor_total,
    get_default_company,
    get_fixed_cost_total_for_period,
    get_monthly_net_profit_from_profit_and_loss,
    get_other_income_total,
    get_rcp_totals,
    get_cogs_total_for_period,
    get_company_currency,
    get_monthly_sales_from_profit_and_loss,
    get_reporting_currency,
    get_sales_total_for_period,
    get_stock_total,
    get_tax_total,
)


SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_INDEX = {label: index + 1 for index, label in enumerate(SHORT_MONTHS)}
RETURN_ADJUSTMENT_ITEM_FILTER = """
    AND TRIM(COALESCE(sii.item_name, '')) NOT IN ('Диллерский бонус', 'Скидка 3 %%', 'Скидка 7 %%')
    AND TRIM(COALESCE(sii.item_code, '')) NOT IN ('Диллерский бонус', 'Скидка 3 %%', 'Скидка 7 %%')
"""
RETURN_KG_ITEM_FILTER = """
    AND TRIM(COALESCE(sii.item_name, '')) != 'Логистика ГП'
    AND TRIM(COALESCE(sii.item_code, '')) != 'Логистика ГП'
    AND (sii.stock_uom = 'кг' OR sii.uom = 'кг')
"""


def get_context(context):
    context.no_cache = 1


def _month_no(month: str | int | None) -> int | None:
    if month in (None, ""):
        return None
    if isinstance(month, int):
        return month if 1 <= month <= 12 else None

    value = str(month).strip()
    if value.isdigit():
        parsed = cint(value)
        return parsed if 1 <= parsed <= 12 else None

    return MONTH_INDEX.get(value[:3].title())


def _safe_div(numerator: float, denominator: float) -> float:
    return flt(numerator) / flt(denominator) if flt(denominator) else 0


def _get_period_window(year: str, month: str) -> tuple[str, str]:
    month_no = _month_no(month) or 1
    start_date = f"{cint(year)}-{month_no:02d}-01"
    selected_month_start = getdate(start_date)
    today_date = getdate(today())

    if selected_month_start.year == today_date.year and selected_month_start.month == today_date.month:
        end_date = str(today_date)
    else:
        end_date = str(get_last_day(start_date))

    return start_date, end_date


def _compact_number(value: float, precision: int = 1) -> str:
    absolute = abs(flt(value))
    suffix = ""
    divisor = 1
    effective_precision = precision
    if absolute >= 1_000_000_000:
        divisor = 1_000_000_000
        suffix = "B"
        effective_precision = 3
    elif absolute >= 1_000_000:
        divisor = 1_000_000
        suffix = "M"
    elif absolute >= 1_000:
        divisor = 1_000
        suffix = "K"

    if suffix:
        compact = flt(value) / divisor
        factor = 10 ** effective_precision
        truncated = math.trunc(compact * factor) / factor
        text = f"{truncated:.{effective_precision}f}".rstrip("0").rstrip(".")
        return f"{text}{suffix}"

    return format_number(value, precision=0)


def _compact_money_label(value: float, precision: int = 1) -> str:
    compact = _compact_number(value, precision=precision)
    if compact and compact[-1].isalpha():
        return f"{compact[:-1]} {compact[-1]}"
    return compact


def _format_money(value: float) -> str:
    return f"{format_number(value, precision=2)} {get_reporting_currency()}"


def _format_uzs(value: float) -> str:
    return f"{format_number(value, precision=2)} UZS"


def _convert_to_uzs(amount: float | int | None, from_currency: str | None, transaction_date: Any) -> float:
    value = flt(amount)
    source_currency = from_currency or "UZS"
    if not value or source_currency == "UZS":
        return value

    normalized_date = str(getdate(transaction_date or today()))
    direct = frappe.get_all(
        "Currency Exchange",
        fields=["exchange_rate"],
        filters={
            "from_currency": source_currency,
            "to_currency": "UZS",
            "date": ("<=", normalized_date),
        },
        order_by="date desc",
        limit=1,
    )
    if direct and flt(direct[0].exchange_rate):
        return value * flt(direct[0].exchange_rate)

    reverse = frappe.get_all(
        "Currency Exchange",
        fields=["exchange_rate"],
        filters={
            "from_currency": "UZS",
            "to_currency": source_currency,
            "date": ("<=", normalized_date),
        },
        order_by="date desc",
        limit=1,
    )
    if reverse and flt(reverse[0].exchange_rate):
        return value / flt(reverse[0].exchange_rate)

    return value


def _format_percent(value: float, precision: int = 1) -> str:
    return f"{flt(value):.{precision}f}%"


def _empty_month_map(default_factory):
    return {month_no: default_factory() for month_no in range(1, 13)}


def _get_dashboard_years() -> list[str]:
    rows = frappe.db.sql(
        """
        SELECT DISTINCT YEAR(posting_date) AS year
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND posting_date IS NOT NULL
        ORDER BY year
        """,
        as_dict=True,
    )
    years = [str(row.year) for row in rows if row.year]
    if years:
        return years
    return [str(getdate(today()).year)]


def _get_latest_posting_date(year: str) -> Any:
    return frappe.db.sql(
        """
        SELECT MAX(posting_date) AS posting_date
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND YEAR(posting_date) = %(year)s
        """,
        {"year": cint(year)},
        as_dict=True,
    )[0].posting_date


def _resolve_filters(year: str | None = None, month: str | None = None) -> dict[str, Any]:
    years = _get_dashboard_years()
    selected_year = str(year) if year and str(year) in years else years[-1]
    latest_posting_date = _get_latest_posting_date(selected_year)
    default_month = SHORT_MONTHS[getdate(latest_posting_date).month - 1] if latest_posting_date else SHORT_MONTHS[0]
    selected_month = month[:3].title() if month and month[:3].title() in MONTH_INDEX else default_month
    return {
        "years": years,
        "selected_year": selected_year,
        "months": SHORT_MONTHS,
        "selected_month": selected_month,
    }


def _get_period_params(year: str, month: str | None = None) -> dict[str, int]:
    params = {"year": cint(year)}
    month_no = _month_no(month)
    if month_no:
        params["month"] = month_no
    return params


def _period_clause(year: str, month: str | None = None, alias: str = "") -> tuple[str, dict[str, int]]:
    prefix = f"{alias}." if alias else ""
    params = _get_period_params(year, month)
    clause = f" AND YEAR({prefix}posting_date) = %(year)s"
    if "month" in params:
        clause += f" AND MONTH({prefix}posting_date) = %(month)s"
    return clause, params


@lru_cache(maxsize=12)
def _get_monthly_sales_metrics(year: str) -> dict[int, dict[str, float]]:
    clause, params = _period_clause(year)
    rows = frappe.db.sql(
        f"""
        SELECT
            MONTH(si.posting_date) AS month_no,
            si.posting_date,
            si.currency,
            si.company,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0)) AS qty_total,
            SUM(COALESCE(sii.amount, sii.net_amount, 0)) AS sales_amount,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0) * COALESCE(sii.incoming_rate, 0)) AS cost_amount,
            SUM(COALESCE(sii.discount_amount, 0) + COALESCE(sii.distributed_discount_amount, 0)) AS discount_total,
            SUM(
                CASE
                    WHEN COALESCE(sii.is_free_item, 0) = 1
                        THEN COALESCE(sii.price_list_rate, 0) * COALESCE(sii.qty, 0)
                    ELSE 0
                END
            ) AS bonus_total
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
        {clause}
        GROUP BY MONTH(si.posting_date), si.posting_date, si.currency, si.company
        """,
        params,
        as_dict=True,
    )

    month_map = _empty_month_map(lambda: {"qty_total": 0.0, "sales_amount": 0.0, "cost_amount": 0.0, "discount_total": 0.0, "bonus_total": 0.0})
    for row in rows:
        month_map[row.month_no]["qty_total"] += flt(row.qty_total)
        month_map[row.month_no]["cost_amount"] += convert_company_currency_amount(
            row.cost_amount, row.posting_date, row.company
        )
        month_map[row.month_no]["discount_total"] += convert_to_reporting_currency(
            row.discount_total, row.currency, row.posting_date, row.company
        )
        month_map[row.month_no]["bonus_total"] += convert_to_reporting_currency(
            row.bonus_total, row.currency, row.posting_date, row.company
        )

    sales_amounts = get_monthly_sales_from_profit_and_loss(year)
    for month_no in range(1, 13):
        month_map[month_no]["sales_amount"] = flt(sales_amounts.get(month_no))
    return month_map


@lru_cache(maxsize=12)
def _get_monthly_return_metrics(year: str) -> dict[int, dict[str, float]]:
    clause, params = _period_clause(year, alias="si")
    rows = frappe.db.sql(
        f"""
        SELECT
            MONTH(si.posting_date) AS month_no,
            si.posting_date,
            si.currency,
            si.company,
            SUM(ABS(COALESCE(sii.stock_qty, sii.qty, 0))) AS qty_total,
            SUM(ABS(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0))) AS return_amount,
            MAX(COALESCE(si.loyalty_amount, 0)) AS loyalty_bonus
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 1
          {RETURN_ADJUSTMENT_ITEM_FILTER}
          {RETURN_KG_ITEM_FILTER}
        {clause}
        GROUP BY MONTH(si.posting_date), si.posting_date, si.currency, si.company, si.name
        """,
        params,
        as_dict=True,
    )

    bonus_rows = frappe.db.sql(
        f"""
        SELECT
            MONTH(si.posting_date) AS month_no,
            si.posting_date,
            si.currency,
            si.company,
            SUM(ABS(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0))) AS dealer_bonus
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 1
          AND (
              TRIM(COALESCE(sii.item_name, '')) = 'Диллерский бонус'
              OR TRIM(COALESCE(sii.item_code, '')) = 'Диллерский бонус'
          )
        {clause}
        GROUP BY MONTH(si.posting_date), si.posting_date, si.currency, si.company
        """,
        params,
        as_dict=True,
    )

    month_map = _empty_month_map(
        lambda: {"return_qty_total": 0.0, "return_amount": 0.0, "loyalty_bonus": 0.0, "return_bonus_total": 0.0}
    )
    for row in rows:
        month_map[row.month_no]["return_qty_total"] += flt(row.qty_total)
        month_map[row.month_no]["return_amount"] += convert_to_reporting_currency(
            row.return_amount, row.currency, row.posting_date, row.company
        )
        month_map[row.month_no]["loyalty_bonus"] += convert_to_reporting_currency(
            row.loyalty_bonus, row.currency, row.posting_date, row.company
        )
    for row in bonus_rows:
        month_map[row.month_no]["return_bonus_total"] += convert_to_reporting_currency(
            row.dealer_bonus, row.currency, row.posting_date, row.company
        )
    return month_map


def _to_tons(quantity: float) -> float:
    quantity_value = flt(quantity)
    if abs(quantity_value) >= 1000:
        return quantity_value / 1000
    return quantity_value


def _get_sales_volume_data(year: str) -> dict[str, Any]:
    sales_metrics = _get_monthly_sales_metrics(year)
    series = []
    for month_no, month_label in enumerate(SHORT_MONTHS, start=1):
        row = sales_metrics[month_no]
        tons = _to_tons(row["qty_total"])
        amount = flt(row["sales_amount"])
        series.append(
            {
                "month": month_label,
                "tons": round(tons, 2),
                "tons_display": f"{round(tons, 1):g}t" if tons else "",
                "amount": amount,
                "amount_display": _compact_number(amount) if amount else "",
            }
        )
    return {"series": series}


def _get_returns_analysis_data(year: str) -> dict[str, Any]:
    return_metrics = _get_monthly_return_metrics(year)
    series = []
    for month_no, month_label in enumerate(SHORT_MONTHS, start=1):
        row = return_metrics[month_no]
        kg = flt(row["return_qty_total"])
        amount = flt(row["return_amount"])
        series.append(
            {
                "month": month_label,
                "tons": round(kg, 2),
                "tons_display": f"{round(kg, 1):g} кг" if kg else "",
                "amount": amount,
                "amount_display": _compact_number(amount) if amount else "",
            }
        )
    return {"series": series}


def _get_profitability_chart_data(year: str) -> dict[str, Any]:
    sales_metrics = _get_monthly_sales_metrics(year)
    net_profit_metrics = get_monthly_net_profit_from_profit_and_loss(year)
    series = []

    for month_no, month_label in enumerate(SHORT_MONTHS, start=1):
        sales_amount = flt(sales_metrics[month_no]["sales_amount"])
        net_profit_amount = flt(net_profit_metrics.get(month_no))
        profitability_percent = _safe_div(net_profit_amount * 100, sales_amount)

        series.append(
            {
                "month": month_label,
                "profit": round(net_profit_amount / 1000, 2),
                "profit_display": _compact_money_label(net_profit_amount) if net_profit_amount else "0 K",
                "profitability": round(profitability_percent, 2),
                "profitability_display": _format_percent(profitability_percent),
            }
        )

    return {"series": series}


@lru_cache(maxsize=24)
def _get_period_totals(year: str, month: str | None = None) -> dict[str, float]:
    sales_metrics = _get_monthly_sales_metrics(year)
    return_metrics = _get_monthly_return_metrics(year)

    if month:
        month_no = _month_no(month) or 1
        totals = sales_metrics[month_no].copy()
        totals.update(return_metrics[month_no])
    else:
        totals = {
            "qty_total": sum(flt(row["qty_total"]) for row in sales_metrics.values()),
            "sales_amount": sum(flt(row["sales_amount"]) for row in sales_metrics.values()),
            "cost_amount": sum(flt(row["cost_amount"]) for row in sales_metrics.values()),
            "discount_total": sum(flt(row["discount_total"]) for row in sales_metrics.values()),
            "bonus_total": sum(flt(row["bonus_total"]) for row in sales_metrics.values()),
            "return_amount": sum(flt(row["return_amount"]) for row in return_metrics.values()),
            "loyalty_bonus": sum(flt(row["loyalty_bonus"]) for row in return_metrics.values()),
            "return_bonus_total": sum(flt(row["return_bonus_total"]) for row in return_metrics.values()),
        }

    invoice_clause, invoice_params = _period_clause(year, month)
    invoice_count = frappe.db.sql(
        f"""
        SELECT COUNT(name) AS invoice_count
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
        {invoice_clause}
        """,
        invoice_params,
        as_dict=True,
    )[0]

    totals["invoice_count"] = flt(invoice_count.invoice_count)
    return totals


@lru_cache(maxsize=24)
def _get_average_check_totals_uzs(year: str, month: str | None = None) -> dict[str, float]:
    clause, params = _period_clause(year, month, alias="si")
    rows = frappe.db.sql(
        f"""
        SELECT
            si.posting_date,
            si.currency,
            si.company,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0)) AS qty_total,
            SUM(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0)) AS sales_amount,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0) * COALESCE(sii.incoming_rate, 0)) AS cost_amount
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          {clause}
        GROUP BY si.posting_date, si.currency, si.company
        """,
        params,
        as_dict=True,
    )

    return {
        "qty_total": sum(flt(row.qty_total) for row in rows),
        "sales_amount": sum(_convert_to_uzs(row.sales_amount, row.currency, row.posting_date) for row in rows),
        "cost_amount": sum(
            _convert_to_uzs(row.cost_amount, get_company_currency(row.company), row.posting_date)
            for row in rows
        ),
    }


@lru_cache(maxsize=24)
def _get_manufactured_qty(year: str, month: str | None = None) -> float:
    params = {"year": cint(year)}
    month_no = _month_no(month)
    month_clause = ""
    if month_no:
        params["month"] = month_no
        month_clause = " AND MONTH(se.posting_date) = %(month)s"

    row = frappe.db.sql(
        f"""
        SELECT
            SUM(entry_qty) AS manufactured_qty
        FROM (
            SELECT
                se.name,
                SUM(CASE WHEN COALESCE(sed.is_finished_item, 0) = 1 THEN COALESCE(sed.qty, 0) ELSE 0 END) AS entry_qty
            FROM `tabStock Entry` se
            LEFT JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
              AND (se.stock_entry_type = 'Manufacture' OR se.purpose = 'Manufacture')
              AND YEAR(se.posting_date) = %(year)s
              {month_clause}
            GROUP BY se.name
        ) manufacture_entries
        """,
        params,
        as_dict=True,
    )[0]

    return flt(row.manufactured_qty)


@lru_cache(maxsize=24)
def _get_manufacturing_cost_total(year: str, month: str | None = None) -> float:
    params = {"year": cint(year)}
    month_no = _month_no(month)
    month_clause = ""
    if month_no:
        params["month"] = month_no
        month_clause = " AND MONTH(se.posting_date) = %(month)s"

    rows = frappe.db.sql(
        f"""
        SELECT
            posting_date,
            company,
            SUM(entry_total_cost) AS total_cost
        FROM (
            SELECT
                se.name,
                se.posting_date,
                se.company,
                SUM(
                    CASE
                        WHEN COALESCE(sed.is_finished_item, 0) = 0
                            THEN ABS(COALESCE(sed.basic_amount, 0))
                        ELSE 0
                    END
                ) + MAX(COALESCE(se.total_additional_costs, 0)) AS entry_total_cost
            FROM `tabStock Entry` se
            LEFT JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
              AND (se.stock_entry_type = 'Manufacture' OR se.purpose = 'Manufacture')
              AND YEAR(se.posting_date) = %(year)s
              {month_clause}
            GROUP BY se.name, se.posting_date, se.company
        ) manufacture_entries
        GROUP BY posting_date, company
        """,
        params,
        as_dict=True,
    )

    total_cost = sum(
        convert_company_currency_amount(row.total_cost, row.posting_date, row.company)
        for row in rows
    )
    if total_cost:
        return total_cost

    fallback_cogs = flt(get_cogs_total(year, month_no))
    fallback_indirect = flt(get_rcp_totals(year, month_no)["indirect_total"])
    return fallback_cogs + fallback_indirect


def _get_margin_bonus_data(year: str, month: str) -> dict[str, Any]:
    totals = _get_period_totals(year, month)
    report_values = _get_sales_expense_group_breakdown(year, month)
    sales_value = flt(totals["sales_amount"])
    expense_groups = report_values
    stock_expenses_value = flt(expense_groups["stock_expenses"])
    production_expenses_value = flt(expense_groups["production_expenses"])
    admin_expenses_value = flt(expense_groups["admin_expenses"])
    selling_expenses_value = flt(expense_groups["selling_expenses"])
    display_denominator = (
        sales_value
        + stock_expenses_value
        + production_expenses_value
        + admin_expenses_value
        + selling_expenses_value
    )
    sales_percent = round(_safe_div(sales_value * 100, display_denominator), 1) if display_denominator else 0
    stock_expenses_percent = round(_safe_div(stock_expenses_value * 100, display_denominator), 1) if display_denominator else 0
    production_expenses_percent = round(_safe_div(production_expenses_value * 100, display_denominator), 1) if display_denominator else 0
    admin_expenses_percent = round(_safe_div(admin_expenses_value * 100, display_denominator), 1) if display_denominator else 0
    selling_expenses_percent = round(_safe_div(selling_expenses_value * 100, display_denominator), 1) if display_denominator else 0
    segments = [
        _margin_bonus_segment("Сумма продаж", sales_value, sales_percent, "#2563eb"),
        _margin_bonus_segment("Stock Expenses", stock_expenses_value, stock_expenses_percent, "#22c55e"),
        _margin_bonus_segment("Общепроизводственные расходы", production_expenses_value, production_expenses_percent, "#f0b429"),
        _margin_bonus_segment("Административные", admin_expenses_value, admin_expenses_percent, "#ef4444"),
        _margin_bonus_segment("Сотув харажатлари", selling_expenses_value, selling_expenses_percent, "#8b5cf6"),
    ]
    return {
        "sales_value": sales_value,
        "stock_expenses_value": stock_expenses_value,
        "production_expenses_value": production_expenses_value,
        "admin_expenses_value": admin_expenses_value,
        "selling_expenses_value": selling_expenses_value,
        "sales_percent": sales_percent,
        "stock_expenses_percent": stock_expenses_percent,
        "production_expenses_percent": production_expenses_percent,
        "admin_expenses_percent": admin_expenses_percent,
        "selling_expenses_percent": selling_expenses_percent,
        "segments": segments,
        "sales_amount_display": f"{_compact_money_label(sales_value)} {get_reporting_currency()}",
        "stock_expenses_amount_display": f"{_compact_money_label(stock_expenses_value)} {get_reporting_currency()}",
        "production_expenses_amount_display": f"{_compact_money_label(production_expenses_value)} {get_reporting_currency()}",
        "admin_expenses_amount_display": f"{_compact_money_label(admin_expenses_value)} {get_reporting_currency()}",
        "selling_expenses_amount_display": f"{_compact_money_label(selling_expenses_value)} {get_reporting_currency()}",
        "sales_percent_display": f"{sales_percent:.1f}%",
        "stock_expenses_percent_display": f"{stock_expenses_percent:.1f}%",
        "production_expenses_percent_display": f"{production_expenses_percent:.1f}%",
        "admin_expenses_percent_display": f"{admin_expenses_percent:.1f}%",
        "selling_expenses_percent_display": f"{selling_expenses_percent:.1f}%",
        "center_value": f"{int(round(sales_percent))}%",
        "center_label": "Сумма продаж",
        "total_amount_display": f"{_compact_money_label(display_denominator)} {get_reporting_currency()}",
    }


def _margin_bonus_segment(label: str, value: float, percent: float, color: str) -> dict[str, Any]:
    return {
        "label": label,
        "value": value,
        "amount_display": f"{_compact_money_label(value)} {get_reporting_currency()}",
        "percent": percent,
        "percent_display": f"{percent:.1f}%",
        "color": color,
    }


@lru_cache(maxsize=24)
def _get_sales_expense_group_breakdown(year: str, month: str) -> dict[str, float]:
    values = {
        "sales": 0.0,
        "stock_expenses": 0.0,
        "production_expenses": 0.0,
        "admin_expenses": 0.0,
        "selling_expenses": 0.0,
    }
    key_by_account = {
        "4000": "sales",
        "5100": "stock_expenses",
        "52001": "production_expenses",
        "52002": "admin_expenses",
        "52003": "selling_expenses",
    }

    period_field = _get_profit_and_loss_period_field(year, month)
    for row in _get_profit_and_loss_rows(year, month):
        account = str(row.get("account") or "")
        account_number = account.split(" - ", 1)[0].strip()
        key = key_by_account.get(account_number)
        if key:
            values[key] = flt(row.get(period_field))

    return values


def _get_profit_and_loss_rows(year: str, month: str) -> list[dict[str, Any]]:
    from erpnext.accounts.report.profit_and_loss_statement import profit_and_loss_statement
    from erpnext.accounts.utils import get_fiscal_year

    month_no = _month_no(month) or 12
    selected_date = str(get_last_day(f"{cint(year)}-{month_no:02d}-01"))
    company = get_default_company()
    fiscal_year = get_fiscal_year(selected_date, company=company)[0] if company else None
    if not company or not fiscal_year:
        return []
    fiscal_year_dates = frappe.db.get_value(
        "Fiscal Year",
        fiscal_year,
        ["year_start_date", "year_end_date"],
        as_dict=True,
    )
    if not fiscal_year_dates:
        return []

    filters = frappe._dict(
        {
            "company": company,
            "filter_based_on": "Fiscal Year",
            "period_start_date": str(fiscal_year_dates.year_start_date),
            "period_end_date": str(fiscal_year_dates.year_end_date),
            "from_fiscal_year": fiscal_year,
            "to_fiscal_year": fiscal_year,
            "periodicity": "Monthly",
            "accumulated_values": 0,
            "include_default_book_entries": 1,
            "presentation_currency": get_reporting_currency(),
        }
    )
    _columns, rows, *_rest = profit_and_loss_statement.execute(filters)
    return rows or []


def _get_profit_and_loss_period_field(year: str, month: str) -> str:
    month_no = _month_no(month) or 12
    return f"{SHORT_MONTHS[month_no - 1].lower()}_{cint(year)}"


def _get_previous_period(year: str, month: str) -> tuple[str, str]:
    month_no = _month_no(month) or 1
    if month_no == 1:
        return str(cint(year) - 1), SHORT_MONTHS[-1]
    return year, SHORT_MONTHS[month_no - 2]


def _get_average_check_data(year: str, month: str) -> dict[str, Any]:
    totals = _get_period_totals(year, month)
    totals_uzs = _get_average_check_totals_uzs(year, month)
    current_qty = flt(totals["qty_total"])
    current_cost_amount = flt(totals["cost_amount"]) or flt(get_cogs_total(year, _month_no(month)))
    current_sales_price = _safe_div(totals["sales_amount"], current_qty)
    current_cost_price = _safe_div(current_cost_amount, current_qty)
    current_sales_price_uzs = _safe_div(totals_uzs["sales_amount"], flt(totals_uzs["qty_total"]))
    current_cost_price_uzs = _safe_div(totals_uzs["cost_amount"], flt(totals_uzs["qty_total"]))
    sales_amount = flt(totals["sales_amount"])
    month_no = _month_no(month) or 12
    period_end = str(get_last_day(f"{cint(year)}-{month_no:02d}-01"))
    debtor_total = _get_debtor_total_cached(period_end)
    health_ratio = _safe_div(debtor_total * 100, sales_amount)
    health_ratio_capped = min(max(health_ratio, 0), 100)

    previous_year, previous_month = _get_previous_period(year, month)
    previous_totals = _get_period_totals(previous_year, previous_month)
    previous_totals_uzs = _get_average_check_totals_uzs(previous_year, previous_month)
    previous_qty = flt(previous_totals["qty_total"])
    previous_cost_amount = flt(previous_totals["cost_amount"]) or flt(get_cogs_total(previous_year, _month_no(previous_month)))
    previous_sales_price = _safe_div(previous_totals["sales_amount"], previous_qty)
    previous_cost_price = _safe_div(previous_cost_amount, previous_qty)
    previous_sales_price_uzs = _safe_div(previous_totals_uzs["sales_amount"], flt(previous_totals_uzs["qty_total"]))
    previous_cost_price_uzs = _safe_div(previous_totals_uzs["cost_amount"], flt(previous_totals_uzs["qty_total"]))

    sales_change = _safe_div((current_sales_price_uzs - previous_sales_price_uzs) * 100, previous_sales_price_uzs)
    cost_change = _safe_div((current_cost_price_uzs - previous_cost_price_uzs) * 100, previous_cost_price_uzs)

    return {
        "selling_price": current_sales_price,
        "selling_price_display": _format_uzs(current_sales_price_uzs),
        "selling_change": sales_change,
        "selling_change_display": _format_percent(sales_change),
        "cost_price": current_cost_price,
        "cost_price_display": _format_uzs(current_cost_price_uzs),
        "cost_change": cost_change,
        "cost_change_display": _format_percent(cost_change),
        "health_ratio": health_ratio,
        "health_ratio_display": _format_percent(health_ratio),
        "health_ratio_capped": health_ratio_capped,
        "health_sales_display": _format_money(sales_amount),
        "health_debt_display": _format_money(debtor_total),
    }


def _get_unit_cost_data(year: str, month: str) -> dict[str, Any]:
    previous_year, previous_month = _get_previous_period(year, month)
    previous_month_no = _month_no(previous_month)
    manufactured_qty = flt(_get_manufactured_qty(previous_year, previous_month))
    production_cost = flt(_get_manufacturing_cost_total(previous_year, previous_month))
    unit_cost = _safe_div(production_cost, manufactured_qty)
    period_label = f"{previous_month} {previous_year}"

    return {
        "title": "1 kg kolbasa uchun xarajat",
        "period_label": period_label,
        "unit_cost": unit_cost,
        "unit_cost_display": _format_money(unit_cost),
        "production_cost": production_cost,
        "production_cost_display": _format_money(production_cost),
        "manufactured_qty": manufactured_qty,
        "manufactured_qty_display": f"{format_number(manufactured_qty, precision=2)} kg",
        "formula_label": "O'tgan oy xarajati / ishlab chiqarilgan kg",
        "month_no": previous_month_no,
    }


@lru_cache(maxsize=1)
def _get_inventory_breakdown() -> tuple[dict[str, float], dict[str, float]]:
    rows = frappe.db.sql(
        """
        SELECT
            bin.warehouse,
            wh.warehouse_type,
            %(today)s AS posting_date,
            SUM(COALESCE(bin.stock_value, 0)) AS stock_value
        FROM `tabBin` bin
        INNER JOIN `tabWarehouse` wh ON wh.name = bin.warehouse
        WHERE wh.disabled = 0
          AND wh.is_group = 0
        GROUP BY bin.warehouse, wh.warehouse_type
        HAVING SUM(COALESCE(bin.stock_value, 0)) <> 0
        ORDER BY SUM(COALESCE(bin.stock_value, 0)) DESC
        """,
        {"today": str(getdate(today()))},
        as_dict=True,
    )

    stock_rows: dict[str, float] = {}
    wip_rows: dict[str, float] = {}
    for row in rows:
        warehouse_name = str(row.warehouse or "")
        warehouse_type = str(row.warehouse_type or "")
        stock_value = convert_company_currency_amount(row.stock_value, row.posting_date)
        classification_key = f"{warehouse_name} {warehouse_type}".lower()
        if "work in progress" in classification_key or "wip" in classification_key or "hsu" in classification_key:
            wip_rows[warehouse_name] = stock_value
        else:
            stock_rows[warehouse_name] = stock_value

    return stock_rows, wip_rows


def _top_breakdown_rows(rows: dict[str, float], empty_label: str) -> list[list[str]]:
    if not rows:
        return [[empty_label, f"0 {get_reporting_currency()}"], ["Tracked Warehouses", "0"]]

    sorted_rows = sorted(rows.items(), key=lambda item: item[1], reverse=True)
    top_label, top_value = sorted_rows[0]
    return [
        [top_label, _format_money(top_value)],
        ["Tracked Warehouses", str(len(sorted_rows))],
    ]


@lru_cache(maxsize=24)
def _get_party_balance_rows(account_type: str, year: str, month: str) -> dict[str, float]:
    month_no = _month_no(month) or 12
    period_end = str(get_last_day(f"{cint(year)}-{month_no:02d}-01"))

    if account_type == "Payable":
        return _get_payable_outstanding_rows(year, month)
    if account_type == "Receivable":
        return get_debtor_balance_rows(period_end=period_end)

    period_start = f"{cint(year)}-{month_no:02d}-01"
    balance_direction = "1" if account_type == "Receivable" else "-1"
    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), acc.account_name, acc.name) AS party_label,
            gle.posting_date,
            gle.company,
            ({balance_direction} * SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0))) AS balance
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.is_cancelled = 0
          AND acc.is_group = 0
          AND acc.account_type = %(account_type)s
          AND gle.posting_date <= LAST_DAY(%(period_start)s)
        GROUP BY COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), acc.account_name, acc.name), gle.posting_date, gle.company
        ORDER BY balance DESC, party_label ASC
        """,
        {"account_type": account_type, "period_start": period_start},
        as_dict=True,
    )

    balances_by_party: dict[str, float] = {}
    for row in rows:
        party_label = str(row.party_label or "Unknown")
        balances_by_party[party_label] = balances_by_party.get(party_label, 0) + convert_company_currency_amount(
            row.balance, row.posting_date, row.company
        )

    return {
        party_label: balance
        for party_label, balance in balances_by_party.items()
        if flt(balance) > 0
    }


@lru_cache(maxsize=24)
def _get_payable_outstanding_rows(year: str, month: str) -> dict[str, float]:
    month_no = _month_no(month) or 12
    period_end = f"{cint(year)}-{month_no:02d}-01"
    payable_accounts = frappe.get_all(
        "Account",
        filters={
            "account_type": "Payable",
            "disabled": 0,
            "is_group": 0,
        },
        or_filters={
            "account_number": ("like", "2111%"),
            "name": ("like", "2111%"),
        },
        pluck="name",
    )

    if not payable_accounts:
        payable_accounts = frappe.get_all(
            "Account",
            filters={
                "account_type": "Payable",
                "disabled": 0,
                "is_group": 0,
                "name": ("like", "Creditors%"),
            },
            pluck="name",
        )

    rows = frappe.db.sql(
        """
        SELECT
            COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), gle.account) AS party_label,
            gle.posting_date,
            gle.company,
            SUM(COALESCE(gle.credit, 0) - COALESCE(gle.debit, 0)) AS balance
        FROM `tabGL Entry` gle
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND gle.account IN %(accounts)s
          AND gle.posting_date <= LAST_DAY(%(period_end)s)
        GROUP BY COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), gle.account), gle.posting_date, gle.company
        ORDER BY party_label ASC
        """,
        {"accounts": tuple(payable_accounts), "period_end": period_end},
        as_dict=True,
    )

    balances_by_party: dict[str, float] = {}
    for row in rows:
        balance = flt(row.balance)
        if not balance:
            continue

        party_label = str(row.party_label or "Unknown")
        balances_by_party[party_label] = balances_by_party.get(party_label, 0) + convert_company_currency_amount(
            balance, row.posting_date, row.company
        )

    return {
        party_label: balance
        for party_label, balance in balances_by_party.items()
        if flt(balance)
    }


def _top_party_breakdown_rows(rows: dict[str, float], empty_label: str) -> list[list[str]]:
    if not rows:
        return [[empty_label, f"0 {get_reporting_currency()}"], ["Tracked Parties", "0"]]

    sorted_rows = sorted(rows.items(), key=lambda item: item[1], reverse=True)
    top_label, top_value = sorted_rows[0]
    return [
        [top_label, _format_money(top_value)],
        ["Tracked Parties", str(len(sorted_rows))],
    ]


def _get_balance_details_data(year: str, month: str) -> dict[str, Any]:
    month_no = _month_no(month) or 12
    period_end = str(get_last_day(f"{cint(year)}-{month_no:02d}-01"))
    cash_total = _get_cash_total_cached(period_end)
    stock_total = _get_stock_total_cached(period_end)
    debtor_total = _get_debtor_total_cached(period_end)
    creditor_total = _get_creditor_total_cached(period_end)

    items = [
        {
            "label": "Склад",
            "value": _format_money(stock_total),
        },
        {
            "label": "Дебитор",
            "value": _format_money(debtor_total),
        },
        {
            "label": "Кредитор",
            "value": _format_money(creditor_total),
        },
        {
            "label": "Касса",
            "value": _format_money(cash_total),
        },
    ]

    return {
        "items": items,
        "total_balance": _format_money(stock_total + debtor_total - creditor_total + cash_total),
    }


@lru_cache(maxsize=24)
def _get_debtor_total_cached(period_end: str) -> float:
    return get_debtor_total(period_end=period_end)


@lru_cache(maxsize=24)
def _get_creditor_total_cached(period_end: str) -> float:
    return get_creditor_total(period_end=period_end)


@lru_cache(maxsize=24)
def _get_stock_total_cached(period_end: str) -> float:
    return get_stock_total(period_end=period_end)


@lru_cache(maxsize=24)
def _get_cash_total_cached(period_end: str) -> float:
    return get_cash_total(period_end=period_end)


@lru_cache(maxsize=24)
def _get_break_even_metrics(year: str, month: str) -> dict[str, float]:
    from_date, to_date = _get_period_window(year, month)
    month_no = _month_no(month) or 1

    sales_rows = frappe.db.sql(
        """
        SELECT
            si.posting_date,
            si.currency,
            si.company,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0)) AS qty_total
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY si.posting_date, si.currency, si.company
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    manufactured_qty = flt(_get_manufactured_qty(year, month))
    current_qty = sum(flt(row.qty_total) for row in sales_rows)
    sales_amount = flt(get_monthly_sales_from_profit_and_loss(year).get(month_no))
    cost_amount = flt(get_cogs_total_for_period(from_date, to_date))
    fixed_cost_total = flt(get_fixed_cost_total_for_period(from_date, to_date))

    if to_date != str(get_last_day(from_date)):
        sales_amount = flt(get_sales_total_for_period(from_date, to_date))
        cost_amount = flt(get_cogs_total_for_period(from_date, to_date))
        fixed_cost_total = flt(get_fixed_cost_total_for_period(from_date, to_date))
        manufactured_qty = flt(_get_manufactured_qty_for_period(from_date, to_date))

    return {
        "qty_total": current_qty,
        "manufactured_qty": manufactured_qty,
        "sales_amount": sales_amount,
        "cost_amount": cost_amount,
        "fixed_cost_total": fixed_cost_total,
    }


@lru_cache(maxsize=24)
def _get_manufactured_qty_for_period(from_date: str, to_date: str) -> float:
    row = frappe.db.sql(
        """
        SELECT
            SUM(entry_qty) AS manufactured_qty
        FROM (
            SELECT
                se.name,
                SUM(CASE WHEN COALESCE(sed.is_finished_item, 0) = 1 THEN COALESCE(sed.qty, 0) ELSE 0 END) AS entry_qty
            FROM `tabStock Entry` se
            LEFT JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
              AND (se.stock_entry_type = 'Manufacture' OR se.purpose = 'Manufacture')
              AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY se.name
        ) manufacture_entries
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=True,
    )[0]

    return flt(row.manufactured_qty)


@lru_cache(maxsize=48)
def _get_expense_total_by_root_for_period(
    from_date: str,
    to_date: str,
    root_account_patterns: tuple[str, ...] | list[str],
    exclude_account_patterns: tuple[str, ...] | list[str] | None = None,
) -> float:
    root_account_patterns = list(root_account_patterns or [])
    exclude_account_patterns = list(exclude_account_patterns or [])
    if not root_account_patterns:
        return 0

    pattern_conditions = " OR ".join(
        " OR ".join(
            [
                f"root_acc.name = {frappe.db.escape(pattern)}",
                f"root_acc.name LIKE {frappe.db.escape(pattern + ' - %')}",
                f"root_acc.name LIKE {frappe.db.escape('% - ' + pattern + ' - %')}",
                f"root_acc.name LIKE {frappe.db.escape('% - ' + pattern)}",
            ]
        )
        for pattern in root_account_patterns
    )
    exclude_conditions = " OR ".join(
        " OR ".join(
            [
                f"exclude_acc.name = {frappe.db.escape(pattern)}",
                f"exclude_acc.name LIKE {frappe.db.escape(pattern + ' - %')}",
                f"exclude_acc.name LIKE {frappe.db.escape('% - ' + pattern + ' - %')}",
                f"exclude_acc.name LIKE {frappe.db.escape('% - ' + pattern)}",
            ]
        )
        for pattern in exclude_account_patterns
    )
    exclude_clause = (
        f"""
          AND NOT EXISTS (
              SELECT 1
              FROM `tabAccount` exclude_acc
              WHERE ({exclude_conditions})
                AND acc.lft >= exclude_acc.lft
                AND acc.rgt <= exclude_acc.rgt
          )
        """
        if exclude_conditions
        else ""
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            gle.posting_date,
            gle.company,
            ABS(IFNULL(SUM(gle.debit - gle.credit), 0)) AS total
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND EXISTS (
              SELECT 1
              FROM `tabAccount` root_acc
              WHERE ({pattern_conditions})
                AND acc.lft >= root_acc.lft
                AND acc.rgt <= root_acc.rgt
          )
          {exclude_clause}
        GROUP BY gle.posting_date, gle.company
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.total, row.posting_date, row.company) for row in rows)


def _get_break_even_data(year: str, month: str) -> dict[str, Any]:
    metrics = _get_break_even_metrics(year, month)
    average_check = _get_average_check_data(year, month)
    current_tons = _to_tons(metrics["manufactured_qty"]) or _to_tons(metrics["qty_total"])
    selling_price = flt(average_check.get("selling_price"))
    cost_price = flt(average_check.get("cost_price"))
    contribution_per_kg = max(selling_price - cost_price, 0)
    plan_kg = _safe_div(metrics["fixed_cost_total"], contribution_per_kg) if contribution_per_kg else 0
    plan_tons = _to_tons(plan_kg)
    plan_tons = round(plan_tons, 2)
    current_tons = round(current_tons, 2)
    max_tons = max(plan_tons, current_tons, 1)
    plan_ratio = min(_safe_div(plan_tons * 100, max_tons), 100)
    current_ratio = min(_safe_div(current_tons * 100, max_tons), 100)

    month_no = _month_no(month) or 12
    period_end = str(get_last_day(f"{cint(year)}-{month_no:02d}-01"))
    debt_total = flt(_get_debtor_total_cached(period_end) or 0)
    debt_vs_sales_total = debt_total + flt(metrics["sales_amount"])
    debt_ratio = _safe_div(debt_total * 100, debt_vs_sales_total)
    sales_ratio = 100 - debt_ratio if debt_vs_sales_total else 0

    return {
        "summary": f"{current_tons:g}t / {plan_tons:g}t",
        "title": "Производственный прогресс",
        "plan_ratio": plan_ratio,
        "current_ratio": current_ratio,
        "start_label": "0t",
        "plan_label": f"План: {plan_tons:g}t",
        "current_label": f"Текущее: {current_tons:g}t",
        "debt_sales_label": f"{round(debt_ratio):g}% / {round(sales_ratio):g}%",
    }


@frappe.whitelist()
def get_dashboard_data(year: str | None = None, month: str | None = None) -> dict[str, Any]:
    _get_monthly_sales_metrics.cache_clear()
    _get_monthly_return_metrics.cache_clear()
    _get_period_totals.cache_clear()
    _get_average_check_totals_uzs.cache_clear()
    _get_manufactured_qty.cache_clear()
    _get_manufacturing_cost_total.cache_clear()
    _get_inventory_breakdown.cache_clear()
    _get_party_balance_rows.cache_clear()
    _get_payable_outstanding_rows.cache_clear()
    _get_break_even_metrics.cache_clear()
    _get_manufactured_qty_for_period.cache_clear()
    _get_expense_total_by_root_for_period.cache_clear()
    _get_debtor_total_cached.cache_clear()
    _get_creditor_total_cached.cache_clear()
    _get_stock_total_cached.cache_clear()
    _get_cash_total_cached.cache_clear()

    filters = _resolve_filters(year, month)
    selected_year = filters["selected_year"]
    selected_month = filters["selected_month"]

    return {
        "filters": filters,
        "sales_volume": _get_sales_volume_data(selected_year),
        "margin_bonus": _get_margin_bonus_data(selected_year, selected_month),
        "average_check": _get_average_check_data(selected_year, selected_month),
        "balance_details": _get_balance_details_data(selected_year, selected_month),
        "break_even": _get_break_even_data(selected_year, selected_month),
        "unit_cost": _get_unit_cost_data(selected_year, selected_month),
        "returns_analysis": _get_returns_analysis_data(selected_year),
        "net_profit_profitability": _get_profitability_chart_data(selected_year),
    }
