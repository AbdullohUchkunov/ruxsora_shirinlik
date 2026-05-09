"""
Dashboard Sverka Hisoboti — Dashboard qiymatlarini GL Entry bilan solishtiradi.

Tanlangan yil/oy uchun page_dashboard da ko'rsatiladigan qiymatlarni
to'g'ridan-to'g'ri GL Entry va Sales Invoice dan hisoblangan qiymatlar bilan
qiyoslaydi. Farq va farq foizi ko'rsatiladi.
"""

from __future__ import annotations

import calendar

import frappe
from frappe import _
from frappe.utils import flt, getdate

from ext_accounts.ruxsora_app.dashboard_data import (
    MONTH_LABELS,
    convert_company_currency_amount,
    convert_company_currency_amount_like_report,
    get_cogs_total,
    get_default_company,
    get_monthly_sales_from_profit_and_loss,
    get_rcp_totals,
)
from ext_accounts.ruxsora_app.page.page_dashboard.data import (
    _period_end_date,
    _period_start_date,
    get_dashboard_summary,
    get_default_year,
)


RETURN_ADJUSTMENT_ITEM_FILTER = """
    AND TRIM(COALESCE(sii.item_name, '')) NOT IN ('Диллерский бонус', 'Скидка 3 %%', 'Скидка 7 %%')
    AND TRIM(COALESCE(sii.item_code, '')) NOT IN ('Диллерский бонус', 'Скидка 3 %%', 'Скидка 7 %%')
"""


def execute(filters=None):
    filters = filters or {}
    columns = _get_columns()
    data = _get_data(filters)
    return columns, data


def _get_columns():
    return [
        {"label": _("Ko'rsatkich"), "fieldname": "label", "fieldtype": "Data", "width": 260},
        {"label": _("Dashboard"), "fieldname": "dashboard", "fieldtype": "Currency", "width": 160},
        {"label": _("GL Tekshiruv"), "fieldname": "gl_check", "fieldtype": "Currency", "width": 160},
        {"label": _("Farq"), "fieldname": "diff", "fieldtype": "Currency", "width": 140},
        {"label": _("Farq %"), "fieldname": "diff_pct", "fieldtype": "Percent", "width": 100},
        {"label": _("Holat"), "fieldname": "status", "fieldtype": "Data", "width": 120},
    ]


def _get_data(filters):
    year = str(filters.get("year") or get_default_year())
    month_label = filters.get("month") or None
    if month_label not in MONTH_LABELS:
        month_label = None
    company = filters.get("company") or get_default_company()

    # Period boundaries
    period_end = _period_end_date(year, month_label)
    period_start = _period_start_date(year, month_label)

    # ── Dashboard qiymatlari ──────────────────────────────────────────────────
    summary = get_dashboard_summary(year, month_label)
    dash_sales = flt(summary.get("sales_total"))
    dash_cost = flt(summary.get("cost_total"))
    dash_rcp = flt(summary.get("rsp_total"))
    dash_margin = flt(summary.get("margin_total"))
    dash_returns = flt(summary.get("return_total"))

    # ── GL Entry dan to'g'ridan-to'g'ri hisob ────────────────────────────────
    gl_sales = _gl_income_total(year, month_label, company, period_end)
    gl_cogs = _gl_cogs_total(year, month_label, company)
    gl_rcp = flt(get_rcp_totals(year, month_label)["direct_total"])
    gl_returns = _gl_returns_total(year, month_label, company, period_end)
    gl_margin = gl_sales - gl_cogs

    # ── Qatorlar ─────────────────────────────────────────────────────────────
    rows = []

    rows.append(_section(_("DAROMAD (SAVDO)")))
    rows.append(_row(_("Savdo jami (Sales Total)"), dash_sales, gl_sales))

    rows.append(_section(_("TANNARX (COGS)")))
    rows.append(_row(_("Tannarx jami (COGS)"), dash_cost, gl_cogs))

    rows.append(_section(_("TO'G'RIDAN XARAJATLAR (RCP/Direct Expenses)")))
    rows.append(_row(_("RCP (Direct Expenses)"), dash_rcp, gl_rcp))

    rows.append(_section(_("QAYTARIMLAR (RETURNS)")))
    rows.append(_row(_("Qaytarimlar jami"), dash_returns, gl_returns))

    rows.append(_section(_("FOYDA (MARGIN)")))
    rows.append(_row(_("Yalpi foyda (Dashboard: savdo-tannarx-rcp)"), dash_margin, gl_sales - gl_cogs))
    rows.append(_row(_("Sof foyda (savdo - tannarx - rcp)"), dash_margin, gl_sales - gl_cogs - gl_rcp))

    return rows


def _gl_income_total(year: str, month_label: str | None, company: str | None, period_end) -> float:
    """GL Entry dan daromad (Income) hisobi — P&L bilan bir xil usul."""
    monthly_sales = get_monthly_sales_from_profit_and_loss(year)
    if month_label in MONTH_LABELS:
        return flt(monthly_sales.get(MONTH_LABELS.index(month_label) + 1))
    return sum(flt(v) for v in monthly_sales.values())


def _gl_cogs_total(year: str, month_label: str | None, company: str | None) -> float:
    """Stock Ledger → GL Entry dan tannarx hisobi."""
    return flt(get_cogs_total(year, month_label))


def _gl_returns_total(year: str, month_label: str | None, company: str | None, period_end) -> float:
    """Qaytarilgan hisob-fakturalar summasi."""
    month_no = (MONTH_LABELS.index(month_label) + 1) if month_label in MONTH_LABELS else None
    month_filter = f" AND MONTH(si.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            si.posting_date,
            si.currency,
            si.company,
            SUM(ABS(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0))) AS amount
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 1
          AND YEAR(si.posting_date) = %(year)s
          {RETURN_ADJUSTMENT_ITEM_FILTER}
          {month_filter}
        GROUP BY si.posting_date, si.currency, si.company
        """,
        {"year": int(year)},
        as_dict=True,
    )

    from ext_accounts.ruxsora_app.dashboard_data import convert_to_reporting_currency
    return sum(
        convert_to_reporting_currency(row.amount, row.currency, period_end or row.posting_date, row.company)
        for row in rows
    )


def _row(label: str, dashboard: float, gl_check: float) -> dict:
    diff = flt(dashboard) - flt(gl_check)
    diff_pct = (diff / flt(gl_check) * 100) if flt(gl_check) else 0
    abs_pct = abs(diff_pct)

    if abs_pct < 1:
        status = "✓ Mos"
    elif abs_pct < 5:
        status = "⚠ Kichik"
    else:
        status = "✗ Katta farq"

    return {
        "label": label,
        "dashboard": flt(dashboard),
        "gl_check": flt(gl_check),
        "diff": diff,
        "diff_pct": round(diff_pct, 2),
        "status": status,
        "bold": 0,
    }


def _section(label: str) -> dict:
    return {
        "label": label,
        "dashboard": None,
        "gl_check": None,
        "diff": None,
        "diff_pct": None,
        "status": "",
        "bold": 1,
    }
