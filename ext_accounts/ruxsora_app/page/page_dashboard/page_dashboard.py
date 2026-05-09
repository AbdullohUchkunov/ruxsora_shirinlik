from __future__ import annotations

import json
from pathlib import Path

import frappe

from ext_accounts.ruxsora_app.page.page_dashboard.data import (
    get_avg_check_chart_data,
    get_avg_cost_chart_data,
    get_dashboard_years,
    get_dashboard_summary,
    get_default_year,
    get_kg_chart_data,
    get_kpi_client_table_rows,
    get_product_margin_rows,
    get_regional_map_data,
)
from ext_accounts.ruxsora_app.dashboard_data import MONTH_LABELS, format_number

_CACHE_PREFIX = "page_dashboard"
_CACHE_TTL_SECONDS = 300
_DEFAULT_TABLE_LIMIT = 100


TAB_ITEMS = [
    {"label": "ГЛАВНЫЙ", "route": "/app/main-dashboard"},
    {"label": "ПАНЕЛЬ", "route": "/app/page-dashboard", "active": 1},
    {"label": "ЕЖЕДНЕВНО", "route": "/app/daily-dashboard"},
    {"label": "ПРОДАЖА", "route": "/app/sales-dashboard"},
    {"label": "КАССА", "route": "/app/cash-dashboard"},
    {"label": "КЛИЕНТ", "route": "/app/client-dashboard"},
    {"label": "ДИВИДЕНДЫ", "route": "/app/dividend-analysis"},
    {"label": "ЕЖЕМЕСЯЧНО", "route": "/app/monthly-analysis"},
    {"label": "ПОСТАВЩИКИ", "route": "/app/supplier-dashboard"},
]

KPI_ITEMS = [
    {"key": "sales_total", "label": "Сумма продаж"},
    {"key": "cost_total", "label": "Себестоимость"},
    {"key": "margin_total", "label": "Маржа"},
    {"key": "rsp_total", "label": "Сумма РСП"},
    {"key": "return_total", "label": "Сумма возвратов"},
    {"key": "kg_total", "label": "КГ"},
    {"key": "avg_check", "label": "Сред.чек"},
]

_GEOJSON_PATH = Path(
    frappe.get_app_path("ext_accounts", "public", "geojson", "uzbekistan_regions.clean.geojson")
)


def _rows(data):
    rows = []
    for item in data:
        values = item[:]
        is_total = False
        if len(values) and values[-1] is True:
            values = values[:-1]
            is_total = True
        rows.append({"values": values, "is_total": is_total})
    return rows


def _format_kpi_totals(year: str, month: str | None = None) -> dict[str, str]:
    summary = get_dashboard_summary(year, month)
    return {
        "sales_total": format_number(summary.get("sales_total"), precision=0),
        "cost_total": format_number(summary.get("cost_total"), precision=0),
        "margin_total": format_number(summary.get("margin_total"), precision=0),
        "rsp_total": format_number(summary.get("rsp_total"), precision=0),
        "return_total": format_number(summary.get("return_total"), precision=0),
        "kg_total": format_number(summary.get("kg_total"), precision=0),
        "avg_check": format_number(summary.get("avg_check"), precision=0),
    }


def _resolve_period(year: str | None = None, month: str | None = None):
    years = get_dashboard_years()
    default_year = get_default_year()
    selected_year = str(year) if year and str(year) in years else default_year
    selected_month = month if month in MONTH_LABELS else None
    return years, default_year, selected_year, selected_month


def _cache_key(section: str, year: str | None = None, month: str | None = None) -> str:
    return f"{_CACHE_PREFIX}:{section}:{year or 'default'}:{month or 'all'}"


def _cached(section: str, year: str | None, month: str | None, generator):
    key = _cache_key(section, year, month)
    cached_value = frappe.cache().get_value(key)
    if cached_value is not None:
        return cached_value

    value = generator()
    frappe.cache().set_value(key, value, expires_in_sec=_CACHE_TTL_SECONDS)
    return value


def _period_title(year: str, month: str | None = None) -> str:
    return f"Данные за {month} {year}" if month else f"Данные за {year} год"


def clear_dashboard_cache(*args, **kwargs):
    frappe.cache().delete_keys(_CACHE_PREFIX)


@frappe.whitelist()
def get_dashboard_context(year: str | None = None, month: str | None = None):
    years, default_year, selected_year, selected_month = _resolve_period(year, month)

    return _cached(
        "context",
        selected_year,
        selected_month,
        lambda: {
            "tabs": TAB_ITEMS,
            "kpis": KPI_ITEMS,
            "years": years,
            "months": MONTH_LABELS,
            "default_year": default_year,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "kpi_totals": _format_kpi_totals(selected_year, selected_month),
        },
    )


@frappe.whitelist()
def get_chart_data(year: str | None = None, month: str | None = None):
    _, _, selected_year, selected_month = _resolve_period(year, month)
    return _cached(
        "charts",
        selected_year,
        selected_month,
        lambda: {
            "price_trend": get_avg_cost_chart_data(selected_year),
            "check_trend": get_avg_check_chart_data(selected_year),
            "kg_trend": get_kg_chart_data(selected_year),
        },
    )


@frappe.whitelist()
def get_product_margin_data(year: str | None = None, month: str | None = None, limit: int | None = None):
    _, _, selected_year, selected_month = _resolve_period(year, month)
    row_limit = int(limit or _DEFAULT_TABLE_LIMIT)
    return _cached(
        f"product_margin:{row_limit}",
        selected_year,
        selected_month,
        lambda: {
            "title": _period_title(selected_year, selected_month),
            "rows": _rows(get_product_margin_rows(selected_year, selected_month, limit=row_limit)),
        },
    )


@frappe.whitelist()
def get_client_kpi_data(year: str | None = None, month: str | None = None, limit: int | None = None):
    _, _, selected_year, selected_month = _resolve_period(year, month)
    row_limit = int(limit or _DEFAULT_TABLE_LIMIT)
    return _cached(
        f"client_kpi:v3:{row_limit}",
        selected_year,
        selected_month,
        lambda: {
            "title": _period_title(selected_year, selected_month),
            "rows": _rows(get_kpi_client_table_rows(selected_year, selected_month, limit=row_limit)),
        },
    )


@frappe.whitelist()
def get_regional_data(year: str | None = None, month: str | None = None):
    _, _, selected_year, selected_month = _resolve_period(year, month)
    return _cached(
        "regional",
        selected_year,
        selected_month,
        lambda: {"rows": get_regional_map_data(selected_year, selected_month)},
    )


@frappe.whitelist()
def get_regions_geojson():
    return json.loads(_GEOJSON_PATH.read_text(encoding="utf-8"))
