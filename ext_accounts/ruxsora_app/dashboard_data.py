from __future__ import annotations

from typing import Any

import json

import frappe
from frappe.utils import cint, flt, format_datetime, get_first_day, get_last_day, getdate, now_datetime, today

REPORTING_CURRENCY = "USD"

_COMPANY_CURRENCY_CACHE: dict[str, str] = {}
_EXCHANGE_RATE_CACHE: dict[tuple[str, str, str], float] = {}
_DEBTOR_ACCOUNT_CACHE: list[str] | None = None
_CREDITOR_ACCOUNT_CACHE: list[str] | None = None
_SALES_ACCOUNT_CACHE: list[str] | None = None
_STOCK_ACCOUNT_CACHE: list[str] | None = None
_COGS_ROOT_ACCOUNT_CACHE: list[str] | None = None
_MONTHLY_SALES_PL_CACHE: dict[str, dict[int, float]] = {}
_MONTHLY_NET_PROFIT_PL_CACHE: dict[str, dict[int, float]] = {}
_TARGET_DEBTOR_ACCOUNT = "1311 - Debtors UZS - P"
_TARGET_STOCK_ACCOUNT = "1410 - Сырьё склад - P"
_TARGET_SALES_ACCOUNT = "4110 - Sales - P"
_TARGET_COGS_ACCOUNT = "5111 - Cost of Goods Sold - P"
_TARGET_FIXED_COST_ROOT_ACCOUNT_NUMBER = "5200"
_TARGET_CASH_ROOT_ACCOUNT_NUMBER = "1100"
_TARGET_CASH_ACCOUNTS = [
    ("1110 - Наличные UZB - P", "1110"),
    ("1111 - Р/С UZB - P", "1111"),
    ("1112 - Наличные USD - P", "1112"),
]

MONTH_LABELS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

ENGLISH_MONTH_LABELS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

MONTH_LOOKUP = {
    **{label.lower(): index + 1 for index, label in enumerate(MONTH_LABELS)},
    **{label.lower(): index + 1 for index, label in enumerate(ENGLISH_MONTH_LABELS)},
}


def _get_debtor_account_names() -> list[str]:
    global _DEBTOR_ACCOUNT_CACHE

    if _DEBTOR_ACCOUNT_CACHE is not None:
        return _DEBTOR_ACCOUNT_CACHE

    account_filters = {
        "account_type": "Receivable",
        "disabled": 0,
        "is_group": 0,
    }
    debtor_accounts = frappe.get_all(
        "Account",
        filters={**account_filters, "name": _TARGET_DEBTOR_ACCOUNT},
        pluck="name",
    )

    if not debtor_accounts:
        debtor_accounts = frappe.get_all(
            "Account",
            filters={**account_filters, "account_number": "1311"},
            pluck="name",
        )

    if not debtor_accounts:
        debtor_accounts = frappe.get_all(
            "Account",
            filters=account_filters,
            or_filters=[
                ["Account", "name", "like", "1311 - Debtors%"],
                ["Account", "account_name", "like", "Debtors%"],
            ],
            pluck="name",
        )

    _DEBTOR_ACCOUNT_CACHE = list(dict.fromkeys(debtor_accounts))
    return _DEBTOR_ACCOUNT_CACHE


def get_creditor_account_names() -> list[str]:
    global _CREDITOR_ACCOUNT_CACHE

    if _CREDITOR_ACCOUNT_CACHE is not None:
        return _CREDITOR_ACCOUNT_CACHE

    account_filters = {
        "account_type": "Payable",
        "disabled": 0,
        "is_group": 0,
    }
    creditor_accounts = frappe.get_all(
        "Account",
        filters=account_filters,
        or_filters={
            "account_number": ("like", "2111%"),
            "name": ("like", "2111%"),
        },
        pluck="name",
    )

    if not creditor_accounts:
        creditor_accounts = frappe.get_all(
            "Account",
            filters={
                **account_filters,
                "name": ("like", "Creditors%"),
            },
            pluck="name",
        )

    _CREDITOR_ACCOUNT_CACHE = list(dict.fromkeys(creditor_accounts))
    return _CREDITOR_ACCOUNT_CACHE


def get_sales_account_names() -> list[str]:
    global _SALES_ACCOUNT_CACHE

    if _SALES_ACCOUNT_CACHE is not None:
        return _SALES_ACCOUNT_CACHE

    account_filters = {
        "root_type": "Income",
        "report_type": "Profit and Loss",
        "disabled": 0,
        "is_group": 0,
    }
    sales_accounts = frappe.get_all(
        "Account",
        filters={**account_filters, "name": _TARGET_SALES_ACCOUNT},
        pluck="name",
    )

    if not sales_accounts:
        sales_accounts = frappe.get_all(
            "Account",
            filters={**account_filters, "account_number": "4110"},
            pluck="name",
        )

    if not sales_accounts:
        sales_accounts = frappe.get_all(
            "Account",
            filters=account_filters,
            or_filters=[
                ["Account", "name", "like", "4110%"],
                ["Account", "account_name", "like", "Sales%"],
            ],
            pluck="name",
        )

    _SALES_ACCOUNT_CACHE = list(dict.fromkeys(sales_accounts))
    return _SALES_ACCOUNT_CACHE


def get_cogs_account_names() -> list[str]:
    account_filters = {
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "disabled": 0,
        "is_group": 0,
    }
    cogs_accounts = frappe.get_all(
        "Account",
        filters={**account_filters, "name": _TARGET_COGS_ACCOUNT},
        pluck="name",
    )

    if not cogs_accounts:
        cogs_accounts = frappe.get_all(
            "Account",
            filters={**account_filters, "account_number": "5111"},
            pluck="name",
        )

    if not cogs_accounts:
        cogs_accounts = frappe.get_all(
            "Account",
            filters=account_filters,
            or_filters=[
                ["Account", "name", "like", "5111%"],
                ["Account", "account_name", "like", "Cost of Goods Sold%"],
            ],
            pluck="name",
        )

    return list(dict.fromkeys(cogs_accounts))


def get_fixed_cost_account_names() -> list[str]:
    account_filters = {
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "disabled": 0,
    }
    root_account = frappe.db.get_value(
        "Account",
        {**account_filters, "account_number": _TARGET_FIXED_COST_ROOT_ACCOUNT_NUMBER},
        ["lft", "rgt"],
        as_dict=True,
    )

    if root_account:
        fixed_cost_accounts = frappe.get_all(
            "Account",
            filters={
                **account_filters,
                "is_group": 0,
                "lft": (">=", root_account.lft),
                "rgt": ("<=", root_account.rgt),
            },
            pluck="name",
        )
    else:
        fixed_cost_accounts = frappe.get_all(
            "Account",
            filters={
                **account_filters,
                "is_group": 0,
                "account_number": ("like", f"{_TARGET_FIXED_COST_ROOT_ACCOUNT_NUMBER}%"),
            },
            pluck="name",
        )

    return list(dict.fromkeys(fixed_cost_accounts))


def get_reporting_currency() -> str:
    return REPORTING_CURRENCY


def get_default_company() -> str | None:
    return (
        frappe.defaults.get_user_default("Company")
        or frappe.defaults.get_global_default("company")
        or frappe.db.get_value("Company", {}, "name")
    )


def get_company_currency(company: str | None = None) -> str:
    resolved_company = company or get_default_company()
    if not resolved_company:
        return REPORTING_CURRENCY

    if resolved_company not in _COMPANY_CURRENCY_CACHE:
        _COMPANY_CURRENCY_CACHE[resolved_company] = (
            frappe.db.get_value("Company", resolved_company, "default_currency") or REPORTING_CURRENCY
        )

    return _COMPANY_CURRENCY_CACHE[resolved_company]


def _lookup_currency_exchange_rate(from_currency: str, to_currency: str, transaction_date: Any) -> float:
    normalized_date = str(getdate(transaction_date or today()))
    cache_key = (from_currency, to_currency, normalized_date)
    if cache_key in _EXCHANGE_RATE_CACHE:
        return _EXCHANGE_RATE_CACHE[cache_key]

    if not from_currency or not to_currency or from_currency == to_currency:
        _EXCHANGE_RATE_CACHE[cache_key] = 1.0
        return 1.0

    direct = frappe.get_all(
        "Currency Exchange",
        fields=["exchange_rate"],
        filters={
            "from_currency": from_currency,
            "to_currency": to_currency,
            "date": ("<=", normalized_date),
        },
        order_by="date desc",
        limit=1,
    )
    if direct:
        rate = flt(direct[0].exchange_rate)
        _EXCHANGE_RATE_CACHE[cache_key] = rate
        return rate

    reverse = frappe.get_all(
        "Currency Exchange",
        fields=["exchange_rate"],
        filters={
            "from_currency": to_currency,
            "to_currency": from_currency,
            "date": ("<=", normalized_date),
        },
        order_by="date desc",
        limit=1,
    )
    rate = 1 / flt(reverse[0].exchange_rate) if reverse and flt(reverse[0].exchange_rate) else 0
    _EXCHANGE_RATE_CACHE[cache_key] = rate
    return rate


def convert_to_reporting_currency(
    amount: float | int | None,
    from_currency: str | None,
    transaction_date: Any,
    company: str | None = None,
) -> float:
    value = flt(amount)
    if not value:
        return 0

    source_currency = from_currency or get_company_currency(company)
    if source_currency == REPORTING_CURRENCY:
        return value

    rate = _lookup_currency_exchange_rate(source_currency, REPORTING_CURRENCY, transaction_date)
    return value * rate if rate else value


def convert_company_currency_amount(
    amount: float | int | None,
    transaction_date: Any,
    company: str | None = None,
) -> float:
    return convert_to_reporting_currency(amount, get_company_currency(company), transaction_date, company)


def convert_company_currency_amount_like_report(
    amount: float | int | None,
    transaction_date: Any,
    company: str | None = None,
) -> float:
    return convert_company_currency_amount(amount, transaction_date, company)


def get_gl_account_total(account_name: str, period_end: str | None = None) -> float:
    return get_gl_accounts_total([account_name], period_end=period_end)


def get_gl_accounts_total(account_names: list[str], period_end: str | None = None) -> float:
    account_names = [account_name for account_name in account_names if account_name]
    if not account_names:
        return 0

    company = frappe.db.get_value("Account", account_names[0], "company") or get_default_company()
    if not company:
        return 0

    to_date = str(getdate(period_end or today()))
    from erpnext.accounts.report.general_ledger import general_ledger

    filters = frappe._dict(
        {
            "company": company,
            "from_date": "2000-01-01",
            "to_date": to_date,
            "account": json.dumps(account_names),
            "presentation_currency": REPORTING_CURRENCY,
        }
    )
    _columns, rows = general_ledger.execute(filters)

    closing_rows = [
        row for row in rows if not row.get("posting_date") and "Closing" in str(row.get("account") or "")
    ]
    if closing_rows:
        return flt(closing_rows[-1].get("balance"))

    return 0


def get_stock_total(period_end: str | None = None) -> float:
    stock_accounts = _get_stock_account_names()
    return get_gl_accounts_total(stock_accounts, period_end=period_end)


def _get_stock_account_names() -> list[str]:
    global _STOCK_ACCOUNT_CACHE

    if _STOCK_ACCOUNT_CACHE is not None:
        return _STOCK_ACCOUNT_CACHE

    stock_accounts = frappe.get_all(
        "Account",
        filters={"name": _TARGET_STOCK_ACCOUNT, "disabled": 0, "is_group": 0},
        pluck="name",
    )

    if not stock_accounts:
        stock_accounts = frappe.get_all(
            "Account",
            filters={"account_number": "1410", "disabled": 0, "is_group": 0},
            pluck="name",
        )

    if not stock_accounts:
        stock_accounts = frappe.get_all(
            "Account",
            filters={"account_type": "Stock", "root_type": "Asset", "disabled": 0, "is_group": 0},
            pluck="name",
        )

    _STOCK_ACCOUNT_CACHE = list(dict.fromkeys(stock_accounts))
    return _STOCK_ACCOUNT_CACHE


def get_gl_accounts_period_total(account_names: list[str], from_date: str, to_date: str) -> float:
    account_names = [account_name for account_name in account_names if account_name]
    if not account_names:
        return 0

    company = frappe.db.get_value("Account", account_names[0], "company") or get_default_company()
    if not company:
        return 0

    from erpnext.accounts.report.general_ledger import general_ledger

    filters = frappe._dict(
        {
            "company": company,
            "from_date": str(getdate(from_date)),
            "to_date": str(getdate(to_date)),
            "account": json.dumps(account_names),
            "presentation_currency": REPORTING_CURRENCY,
        }
    )
    _columns, rows = general_ledger.execute(filters)

    total_rows = [row for row in rows if not row.get("posting_date") and str(row.get("account") or "").strip("'") == "Total"]
    if not total_rows:
        return 0

    total_row = total_rows[-1]
    return flt(total_row.get("credit")) - flt(total_row.get("debit"))


def get_sales_total_for_period(from_date: str, to_date: str) -> float:
    sales_accounts = get_sales_account_names()
    return get_gl_accounts_period_total(sales_accounts, from_date, to_date)


def get_cogs_total_for_period(from_date: str, to_date: str) -> float:
    cogs_accounts = get_cogs_account_names()
    return abs(get_gl_accounts_period_total(cogs_accounts, from_date, to_date))


def get_fixed_cost_total_for_period(from_date: str, to_date: str) -> float:
    fixed_cost_accounts = get_fixed_cost_account_names()
    return abs(get_gl_accounts_period_total(fixed_cost_accounts, from_date, to_date))


def get_sales_profit_and_loss_period_end(year: str | int) -> Any:
    sales_accounts = set(get_sales_account_names())
    company = frappe.db.get_value("Account", next(iter(sales_accounts), None), "company") or get_default_company()
    if not company or not sales_accounts:
        return None

    return frappe.db.sql(
        """
        SELECT MAX(posting_date) AS posting_date
        FROM `tabGL Entry`
        WHERE company = %(company)s
          AND account IN %(accounts)s
          AND YEAR(posting_date) = %(year)s
          AND docstatus = 1
          AND is_cancelled = 0
        """,
        {
            "company": company,
            "accounts": tuple(sales_accounts),
            "year": cint(year),
        },
        as_dict=True,
    )[0].posting_date


def get_monthly_sales_from_profit_and_loss(year: str) -> dict[int, float]:
    year_key = str(year)
    if year_key in _MONTHLY_SALES_PL_CACHE:
        return _MONTHLY_SALES_PL_CACHE[year_key]

    sales_accounts = set(get_sales_account_names())
    company = frappe.db.get_value("Account", next(iter(sales_accounts), None), "company") or get_default_company()
    if not company or not sales_accounts:
        month_map = {month_no: 0.0 for month_no in range(1, 13)}
        _MONTHLY_SALES_PL_CACHE[year_key] = month_map
        return month_map

    latest_posting_date = get_sales_profit_and_loss_period_end(year)

    if not latest_posting_date:
        month_map = {month_no: 0.0 for month_no in range(1, 13)}
        _MONTHLY_SALES_PL_CACHE[year_key] = month_map
        return month_map

    from erpnext.accounts.report.profit_and_loss_statement import profit_and_loss_statement
    from erpnext.accounts.utils import get_fiscal_year

    fiscal_year = get_fiscal_year(latest_posting_date, company=company)[0]

    filters = frappe._dict(
        {
            "company": company,
            "from_fiscal_year": fiscal_year,
            "to_fiscal_year": fiscal_year,
            "period_start_date": f"{cint(year)}-01-01",
            "period_end_date": str(getdate(latest_posting_date)),
            "filter_based_on": "Date Range",
            "periodicity": "Monthly",
            "accumulated_values": 0,
            "include_default_book_entries": 1,
            "presentation_currency": REPORTING_CURRENCY,
        }
    )
    columns, data, *_rest = profit_and_loss_statement.execute(filters)

    target_row = None
    for row in data:
        if row.get("account") in sales_accounts:
            target_row = row
            break
        account_name = str(row.get("account_name") or "")
        if any(account_name.startswith(account_name_key.split(" - ", 1)[0]) for account_name_key in sales_accounts):
            target_row = row
            break

    month_map = {month_no: 0.0 for month_no in range(1, 13)}
    if target_row:
        for column in columns:
            fieldname = str(column.get("fieldname") or "")
            if "_" not in fieldname:
                continue
            month_label = fieldname.split("_", 1)[0]
            try:
                month_no = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                }[month_label]
            except KeyError:
                continue
            month_map[month_no] = flt(target_row.get(fieldname))

    _MONTHLY_SALES_PL_CACHE[year_key] = month_map
    return month_map


def get_monthly_net_profit_from_profit_and_loss(year: str) -> dict[int, float]:
    year_key = str(year)
    if year_key in _MONTHLY_NET_PROFIT_PL_CACHE:
        return _MONTHLY_NET_PROFIT_PL_CACHE[year_key]

    company = get_default_company()
    if not company:
        month_map = {month_no: 0.0 for month_no in range(1, 13)}
        _MONTHLY_NET_PROFIT_PL_CACHE[year_key] = month_map
        return month_map

    latest_posting_date = frappe.db.sql(
        """
        SELECT MAX(posting_date) AS posting_date
        FROM `tabGL Entry`
        WHERE company = %(company)s
          AND YEAR(posting_date) = %(year)s
          AND docstatus = 1
          AND is_cancelled = 0
        """,
        {"company": company, "year": cint(year)},
        as_dict=True,
    )[0].posting_date

    if not latest_posting_date:
        month_map = {month_no: 0.0 for month_no in range(1, 13)}
        _MONTHLY_NET_PROFIT_PL_CACHE[year_key] = month_map
        return month_map

    from erpnext.accounts.report.profit_and_loss_statement import profit_and_loss_statement
    from erpnext.accounts.utils import get_fiscal_year

    fiscal_year = get_fiscal_year(latest_posting_date, company=company)[0]
    filters = frappe._dict(
        {
            "company": company,
            "from_fiscal_year": fiscal_year,
            "to_fiscal_year": fiscal_year,
            "period_start_date": f"{cint(year)}-01-01",
            "period_end_date": str(getdate(latest_posting_date)),
            "filter_based_on": "Date Range",
            "periodicity": "Monthly",
            "accumulated_values": 0,
            "include_default_book_entries": 1,
            "presentation_currency": REPORTING_CURRENCY,
        }
    )
    columns, data, *_rest = profit_and_loss_statement.execute(filters)

    target_row = next(
        (row for row in data if str(row.get("account") or "").strip("'") == "Profit for the year"),
        None,
    )

    month_map = {month_no: 0.0 for month_no in range(1, 13)}
    if target_row:
        for column in columns:
            fieldname = str(column.get("fieldname") or "")
            if "_" not in fieldname:
                continue
            month_label = fieldname.split("_", 1)[0]
            try:
                month_no = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                }[month_label]
            except KeyError:
                continue
            month_map[month_no] = flt(target_row.get(fieldname))

    _MONTHLY_NET_PROFIT_PL_CACHE[year_key] = month_map
    return month_map


def get_debtor_balance_rows(period_end: str | None = None) -> dict[str, float]:
    debtor_accounts = _get_debtor_account_names()
    if debtor_accounts:
        date_clause = " AND gle.posting_date <= %(period_end)s" if period_end else ""
        params: dict[str, Any] = {"accounts": tuple(debtor_accounts)}
        if period_end:
            params["period_end"] = period_end

        rows = frappe.db.sql(
            f"""
            SELECT
                COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), gle.account) AS party_label,
                gle.posting_date,
                gle.company,
                SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS balance
            FROM `tabGL Entry` gle
            WHERE gle.docstatus = 1
              AND gle.is_cancelled = 0
              AND gle.account IN %(accounts)s
              {date_clause}
            GROUP BY COALESCE(NULLIF(gle.party, ''), NULLIF(gle.against, ''), gle.account), gle.posting_date, gle.company
            ORDER BY party_label ASC
            """,
            params,
            as_dict=True,
        )

        balances_by_party: dict[str, float] = {}
        for row in rows:
            party_label = str(row.party_label or "Unknown")
            balances_by_party[party_label] = balances_by_party.get(party_label, 0) + convert_company_currency_amount(
                row.balance,
                row.posting_date,
                row.company,
            )

        return {
            party_label: balance
            for party_label, balance in balances_by_party.items()
            if flt(balance) > 0
        }

    date_clause = " AND posting_date <= %(period_end)s" if period_end else ""
    params = {"period_end": period_end} if period_end else {}
    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(customer_name, ''), customer) AS party_label,
            posting_date,
            currency,
            company,
            SUM(COALESCE(outstanding_amount, 0)) AS balance
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
          AND COALESCE(outstanding_amount, 0) > 0
          {date_clause}
        GROUP BY customer, customer_name, posting_date, currency, company
        ORDER BY party_label ASC
        """,
        params,
        as_dict=True,
    )

    balances_by_party: dict[str, float] = {}
    for row in rows:
        party_label = str(row.party_label or "Unknown")
        balances_by_party[party_label] = balances_by_party.get(party_label, 0) + convert_to_reporting_currency(
            row.balance,
            row.currency,
            row.posting_date,
            row.company,
        )

    return {
        party_label: balance
        for party_label, balance in balances_by_party.items()
        if flt(balance) > 0
    }


def get_debtor_total(period_end: str | None = None) -> float:
    debtor_accounts = _get_debtor_account_names()
    if debtor_accounts:
        return get_gl_accounts_total(debtor_accounts, period_end=period_end)

    return sum(get_debtor_balance_rows(period_end=period_end).values())


def get_creditor_total(period_end: str | None = None) -> float:
    creditor_accounts = get_creditor_account_names()
    if creditor_accounts:
        return abs(get_gl_accounts_total(creditor_accounts, period_end=period_end))

    return 0


def _get_cash_account_names() -> list[str]:
    cash_accounts = frappe.db.sql(
        """
        SELECT DISTINCT acc.name
        FROM `tabAccount` acc
        INNER JOIN `tabAccount` root_acc
            ON acc.lft >= root_acc.lft
            AND acc.rgt <= root_acc.rgt
            AND acc.company = root_acc.company
        WHERE acc.disabled = 0
          AND acc.is_group = 0
          AND root_acc.disabled = 0
          AND (
              root_acc.account_number = %(root_account_number)s
              OR root_acc.name LIKE %(root_account_name_pattern)s
          )
        """,
        {
            "root_account_number": _TARGET_CASH_ROOT_ACCOUNT_NUMBER,
            "root_account_name_pattern": f"{_TARGET_CASH_ROOT_ACCOUNT_NUMBER} - %",
        },
        pluck=True,
    )

    if not cash_accounts:
        cash_accounts = frappe.get_all(
            "Account",
            filters={
                "account_number": ("like", f"{_TARGET_CASH_ROOT_ACCOUNT_NUMBER}%"),
                "disabled": 0,
                "is_group": 0,
            },
            pluck="name",
        )

    if not cash_accounts:
        for account_name, account_number in _TARGET_CASH_ACCOUNTS:
            resolved_name = frappe.db.get_value("Account", {"name": account_name, "disabled": 0, "is_group": 0}, "name")
            if not resolved_name and account_number:
                resolved_name = frappe.db.get_value(
                    "Account",
                    {"account_number": account_number, "disabled": 0, "is_group": 0},
                    "name",
                )
            if resolved_name:
                cash_accounts.append(str(resolved_name))

    return list(dict.fromkeys(cash_accounts))


def get_cash_total(period_end: str | None = None) -> float:
    cash_accounts = _get_cash_account_names()
    if not cash_accounts:
        return 0

    return sum(get_gl_account_total(account_name, period_end=period_end) for account_name in cash_accounts)


def _month_number(month: str | int | None) -> int | None:
    if month in (None, ""):
        return None

    if isinstance(month, int):
        return month

    month_key = str(month).strip().lower()
    if month_key.isdigit():
        return cint(month_key)

    return MONTH_LOOKUP.get(month_key)


def _period_date_range(
    year: str | int | None = None,
    month: str | int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> tuple[str | None, str | None]:
    if from_date and to_date:
        return str(getdate(from_date)), str(getdate(to_date))

    if not year:
        return None, None

    month_no = _month_number(month)
    if month_no:
        period_start = getdate(f"{int(year)}-{month_no:02d}-01")
        return str(period_start), str(get_last_day(period_start))

    return f"{int(year)}-01-01", f"{int(year)}-12-31"


def _get_expense_total_by_root(
    year: str | int | None,
    month: str | int | None,
    root_account_patterns: list[str],
    company: str | None = None,
    exclude_account_patterns: list[str] | None = None,
) -> float:
    if not year or not root_account_patterns:
        return 0

    month_no = _month_number(month)
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
    exclude_patterns = exclude_account_patterns or []
    exclude_conditions = " OR ".join(
        " OR ".join(
            [
                f"exclude_acc.name = {frappe.db.escape(pattern)}",
                f"exclude_acc.name LIKE {frappe.db.escape(pattern + ' - %')}",
                f"exclude_acc.name LIKE {frappe.db.escape('% - ' + pattern + ' - %')}",
                f"exclude_acc.name LIKE {frappe.db.escape('% - ' + pattern)}",
            ]
        )
        for pattern in exclude_patterns
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
    company_filter = f" AND gle.company = {frappe.db.escape(company)}" if company else ""
    month_filter = f" AND MONTH(gle.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

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
          AND YEAR(gle.posting_date) = {frappe.db.escape(year)}
          {month_filter}
          {company_filter}
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
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.total, row.posting_date, row.company) for row in rows)


def _get_income_total_by_root(
    year: str | int | None,
    month: str | int | None,
    root_account_patterns: list[str],
    company: str | None = None,
) -> float:
    if not year or not root_account_patterns:
        return 0

    month_no = _month_number(month)
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
    company_filter = f" AND gle.company = {frappe.db.escape(company)}" if company else ""
    month_filter = f" AND MONTH(gle.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            gle.posting_date,
            gle.company,
            ABS(IFNULL(SUM(gle.credit - gle.debit), 0)) AS total
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND YEAR(gle.posting_date) = {frappe.db.escape(year)}
          {month_filter}
          {company_filter}
          AND EXISTS (
              SELECT 1
              FROM `tabAccount` root_acc
              WHERE ({pattern_conditions})
                AND acc.lft >= root_acc.lft
                AND acc.rgt <= root_acc.rgt
          )
        GROUP BY gle.posting_date, gle.company
        """,
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.total, row.posting_date, row.company) for row in rows)


def get_rcp_totals(year: str | int | None, month: str | int | None = None) -> dict[str, float]:
    direct_total = _get_expense_total_by_root(
        year,
        month,
        ["Direct Expenses"],
        exclude_account_patterns=["Stock Expenses", "Cost of Goods Sold", "Stock Adjustment"],
    )
    indirect_total = _get_expense_total_by_root(year, month, ["Indirect Expenses"])
    return {
        "direct_total": direct_total,
        "indirect_total": indirect_total,
        "rcp_total": direct_total + indirect_total,
    }


def get_tax_total(year: str | int | None, month: str | int | None = None) -> float:
    return _get_expense_total_by_root(year, month, ["Duties and Taxes", "Taxes"])


def get_other_income_total(year: str | int | None, month: str | int | None = None) -> float:
    return _get_income_total_by_root(year, month, ["Indirect Income", "Other Income"])


def get_stock_ledger_cost_total(year: str | int | None, month: str | int | None = None) -> float:
    if not year:
        return 0

    month_no = _month_number(month)
    month_filter = f" AND MONTH(sle.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            sle.posting_date,
            sle.company,
            SUM(ABS(COALESCE(sle.stock_value_difference, 0))) AS cost_total
        FROM `tabStock Ledger Entry` sle
        WHERE sle.is_cancelled = 0
          AND sle.voucher_type = 'Sales Invoice'
          AND COALESCE(sle.actual_qty, 0) < 0
          AND YEAR(sle.posting_date) = {frappe.db.escape(year)}
          {month_filter}
        GROUP BY sle.posting_date, sle.company
        """,
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.cost_total, row.posting_date, row.company) for row in rows)


def _get_cogs_root_account_names() -> list[str]:
    global _COGS_ROOT_ACCOUNT_CACHE

    if _COGS_ROOT_ACCOUNT_CACHE is not None:
        return _COGS_ROOT_ACCOUNT_CACHE

    roots = frappe.get_all(
        "Account",
        filters={"name": _TARGET_COGS_ACCOUNT, "disabled": 0},
        pluck="name",
    )
    if not roots:
        roots = frappe.get_all(
            "Account",
            filters={"account_name": "Cost of Goods Sold", "disabled": 0},
            pluck="name",
        )
    if not roots:
        roots = frappe.get_all(
            "Account",
            filters={"name": ["like", "%Cost of Goods Sold%"], "disabled": 0},
            pluck="name",
        )

    _COGS_ROOT_ACCOUNT_CACHE = list(dict.fromkeys(str(root) for root in roots if root))
    return _COGS_ROOT_ACCOUNT_CACHE


def get_gl_cogs_total(
    year: str | int | None = None,
    month: str | int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> float:
    period_start, period_end = _period_date_range(year, month, from_date, to_date)
    root_accounts = _get_cogs_root_account_names()
    if not period_start or not period_end or not root_accounts:
        return 0

    rows = frappe.db.sql(
        """
        SELECT
            gle.posting_date,
            gle.company,
            SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS cogs_total
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        INNER JOIN `tabAccount` root_acc
            ON root_acc.name IN %(root_accounts)s
            AND acc.lft >= root_acc.lft
            AND acc.rgt <= root_acc.rgt
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY gle.posting_date, gle.company
        """,
        {
            "root_accounts": tuple(root_accounts),
            "from_date": period_start,
            "to_date": period_end,
        },
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.cogs_total, row.posting_date, row.company) for row in rows)


def get_monthly_gl_cogs_totals(year: str | int | None) -> dict[int, float]:
    if not year:
        return {month_no: 0.0 for month_no in range(1, 13)}

    root_accounts = _get_cogs_root_account_names()
    if not root_accounts:
        return {month_no: 0.0 for month_no in range(1, 13)}

    rows = frappe.db.sql(
        """
        SELECT
            MONTH(gle.posting_date) AS month_no,
            gle.posting_date,
            gle.company,
            SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS cogs_total
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        INNER JOIN `tabAccount` root_acc
            ON root_acc.name IN %(root_accounts)s
            AND acc.lft >= root_acc.lft
            AND acc.rgt <= root_acc.rgt
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY MONTH(gle.posting_date), gle.posting_date, gle.company
        ORDER BY month_no
        """,
        {
            "root_accounts": tuple(root_accounts),
            "from_date": f"{int(year)}-01-01",
            "to_date": f"{int(year)}-12-31",
        },
        as_dict=True,
    )

    totals = {month_no: 0.0 for month_no in range(1, 13)}
    for row in rows:
        totals[cint(row.month_no)] += convert_company_currency_amount(row.cogs_total, row.posting_date, row.company)
    return totals


def get_item_stock_ledger_cost_map(year: str | int | None, month: str | int | None = None) -> dict[str, float]:
    if not year:
        return {}

    month_no = _month_number(month)
    month_filter = f" AND MONTH(sle.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар') AS item_key,
            sle.posting_date,
            sle.company,
            SUM(ABS(COALESCE(sle.stock_value_difference, 0))) AS cost
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabSales Invoice Item` sii ON sii.name = sle.voucher_detail_no
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sle.is_cancelled = 0
          AND sle.voucher_type = 'Sales Invoice'
          AND COALESCE(sle.actual_qty, 0) < 0
          AND si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          AND YEAR(sle.posting_date) = {frappe.db.escape(year)}
          {month_filter}
        GROUP BY COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар'), sle.posting_date, sle.company
        """,
        as_dict=True,
    )

    result: dict[str, float] = {}
    for row in rows:
        result[row.item_key] = result.get(row.item_key, 0) + convert_company_currency_amount(
            row.cost, row.posting_date, row.company
        )
    return result


def get_cogs_total(year: str | int | None, month: str | int | None = None) -> float:
    return get_gl_cogs_total(year, month)


def get_item_cogs_map(year: str | int | None, month: str | int | None = None) -> dict[str, float]:
    return get_item_stock_ledger_cost_map(year, month)


def _get_rcp_expense_total(year: str | int | None, month: str | int | None = None) -> float:
    if not year:
        return 0

    month_no = _month_number(month)
    month_filter = f" AND MONTH(gle.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            gle.posting_date,
            gle.company,
            IFNULL(SUM(gle.debit - gle.credit), 0) AS total
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        INNER JOIN `tabAccount` root_acc ON root_acc.name = '5200 - Indirect Expenses - R'
        WHERE gle.docstatus = 1
          AND gle.is_cancelled = 0
          AND YEAR(gle.posting_date) = %(year)s
          {month_filter}
          AND acc.lft >= root_acc.lft
          AND acc.rgt <= root_acc.rgt
        GROUP BY gle.posting_date, gle.company
        """,
        {"year": int(year)},
        as_dict=True,
    )

    return sum(convert_company_currency_amount(row.total, row.posting_date, row.company) for row in rows)


def _get_item_sales_map_for_rcp(year: str | int, month: int | None = None) -> dict[str, float]:
    month_filter = f" AND MONTH(si.posting_date) = {frappe.db.escape(month)}" if month else ""
    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар') AS item_key,
            si.posting_date,
            si.currency,
            si.company,
            SUM(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0)) AS sales
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          AND YEAR(si.posting_date) = %(year)s
          {month_filter}
        GROUP BY
            COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар'),
            si.posting_date,
            si.currency,
            si.company
        """,
        {"year": int(year)},
        as_dict=True,
    )

    sales_by_item: dict[str, float] = {}
    for row in rows:
        sales_by_item[row.item_key] = sales_by_item.get(row.item_key, 0) + convert_to_reporting_currency(
            row.sales,
            row.currency,
            row.posting_date,
            row.company,
        )

    return sales_by_item


def _allocate_rcp_by_sales_share(rcp_total: float, sales_by_item: dict[str, float]) -> dict[str, float]:
    total_sales = sum(amount for amount in sales_by_item.values() if amount > 0)
    if not rcp_total or not total_sales:
        return {}

    return {
        item_key: (amount / total_sales) * rcp_total
        for item_key, amount in sales_by_item.items()
        if amount > 0
    }


def _get_item_rcp_map_for_month(year: str | int, month: int) -> dict[str, float]:
    return _allocate_rcp_by_sales_share(
        _get_rcp_expense_total(year, month),
        _get_item_sales_map_for_rcp(year, month),
    )


def get_item_rcp_map(year: str | int | None, month: str | int | None = None) -> dict[str, float]:
    if not year:
        return {}

    month_no = _month_number(month)
    if month_no:
        return _get_item_rcp_map_for_month(year, month_no)

    result: dict[str, float] = {}
    for current_month in range(1, 13):
        for item_key, amount in _get_item_rcp_map_for_month(year, current_month).items():
            result[item_key] = result.get(item_key, 0) + amount

    unallocated_amount = _get_rcp_expense_total(year) - sum(result.values())
    for item_key, amount in _allocate_rcp_by_sales_share(
        unallocated_amount,
        _get_item_sales_map_for_rcp(year),
    ).items():
        result[item_key] = result.get(item_key, 0) + amount

    return result


def get_item_bonus_map(year: str | int | None, month: str | int | None = None) -> dict[str, float]:
    if not year:
        return {}

    month_no = _month_number(month)
    month_filter_sales = f" AND MONTH(si.posting_date) = {frappe.db.escape(month_no)}" if month_no else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            sii.parent AS invoice_name,
            COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар') AS item_key,
            si.posting_date,
            si.company,
            si.currency,
            SUM(COALESCE(sii.net_amount, sii.amount, sii.base_net_amount, sii.base_amount, 0)) AS item_sales,
            SUM(
                CASE
                    WHEN COALESCE(sii.is_free_item, 0) = 1
                        THEN COALESCE(sii.price_list_rate, 0) * COALESCE(sii.qty, 0)
                    ELSE 0
                END
            ) AS free_bonus
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          AND YEAR(si.posting_date) = {frappe.db.escape(year)}
          {month_filter_sales}
        GROUP BY
            sii.parent,
            COALESCE(NULLIF(sii.item_code, ''), NULLIF(sii.item_name, ''), 'Неизвестный товар'),
            si.posting_date,
            si.company,
            si.currency
        """,
        as_dict=True,
    )

    item_rows: dict[str, list[dict[str, Any]]] = {}
    invoice_totals: dict[str, float] = {}

    for row in rows:
        invoice_name = str(row.invoice_name or "")
        item_sales = flt(row.item_sales)
        item_rows.setdefault(invoice_name, []).append(
            {
                "item_key": row.item_key,
                "item_sales": item_sales,
                "free_bonus": flt(row.free_bonus),
                "posting_date": row.posting_date,
                "company": row.company,
                "currency": row.currency,
            }
        )
        invoice_totals[invoice_name] = invoice_totals.get(invoice_name, 0) + item_sales

    loyalty_rows = frappe.db.sql(
        f"""
        SELECT
            name AS invoice_name,
            posting_date,
            company,
            currency,
            SUM(COALESCE(loyalty_amount, 0)) AS loyalty_bonus
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
          AND YEAR(posting_date) = {frappe.db.escape(year)}
          {month_filter_sales.replace("si.", "")}
        GROUP BY name, posting_date, company, currency
        """,
        as_dict=True,
    )

    loyalty_by_invoice: dict[str, float] = {}
    for row in loyalty_rows:
        loyalty_by_invoice[str(row.invoice_name or "")] = convert_to_reporting_currency(
            row.loyalty_bonus, row.currency, row.posting_date, row.company
        )

    bonus_map: dict[str, float] = {}
    for invoice_name, items in item_rows.items():
        invoice_total = flt(invoice_totals.get(invoice_name))
        loyalty_bonus = flt(loyalty_by_invoice.get(invoice_name))
        for item in items:
            item_bonus = convert_to_reporting_currency(
                item["free_bonus"], item["currency"], item["posting_date"], item["company"]
            )
            if invoice_total and loyalty_bonus:
                item_bonus += loyalty_bonus * flt(item["item_sales"]) / invoice_total
            bonus_map[item["item_key"]] = bonus_map.get(item["item_key"], 0) + item_bonus

    return bonus_map


def get_reference_month_date():
    latest_posting_date = frappe.db.sql(
        """
        SELECT MAX(posting_date) AS latest_posting_date
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
        """,
        as_dict=True,
    )[0].latest_posting_date

    return getdate(latest_posting_date) if latest_posting_date else getdate(today())


def get_reference_month_range() -> tuple[str, str]:
    reference_date = get_reference_month_date()
    return str(get_first_day(reference_date)), str(get_last_day(reference_date))


def get_reference_month_label() -> str:
    reference_date = get_reference_month_date()
    return reference_date.strftime("%m.%Y")


def format_number(value: Any, precision: int = 0) -> str:
    number = flt(value)
    formatted = f"{number:,.{precision}f}".replace(",", " ")
    if precision > 0:
        formatted = formatted.rstrip("0").rstrip(".")
    else:
        formatted = formatted.split(".")[0]
    return formatted


def get_monthly_sales_kg(year_limit: int = 4) -> list[dict[str, Any]]:
    rows = frappe.db.sql(
        """
        SELECT
            YEAR(si.posting_date) AS year,
            MONTH(si.posting_date) AS month_no,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0)) AS total_kg
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
        GROUP BY YEAR(si.posting_date), MONTH(si.posting_date)
        ORDER BY YEAR(si.posting_date), MONTH(si.posting_date)
        """,
        as_dict=True,
    )

    years = sorted({row.year for row in rows if row.year})
    if year_limit and len(years) > year_limit:
        years = years[-year_limit:]

    monthly_map = {(row.year, row.month_no): flt(row.total_kg) for row in rows if row.year in years}
    result = []
    for year in years:
        values = [round(monthly_map.get((year, month_no), 0)) for month_no in range(1, 13)]
        result.append({"year": year, "values": values})

    return result


def get_monthly_sales_amount(year_limit: int = 2) -> list[dict[str, Any]]:
    rows = frappe.db.sql(
        """
        SELECT
            YEAR(posting_date) AS year,
            MONTH(posting_date) AS month_no,
            posting_date,
            currency,
            company,
            SUM(COALESCE(net_total, 0)) AS total_amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
        GROUP BY YEAR(posting_date), MONTH(posting_date), posting_date, currency, company
        ORDER BY YEAR(posting_date), MONTH(posting_date), posting_date
        """,
        as_dict=True,
    )

    years = sorted({row.year for row in rows if row.year})
    if year_limit and len(years) > year_limit:
        years = years[-year_limit:]

    monthly_map: dict[tuple[int, int], float] = {}
    for row in rows:
        if row.year not in years:
            continue
        key = (row.year, row.month_no)
        monthly_map[key] = monthly_map.get(key, 0) + convert_to_reporting_currency(
            row.total_amount,
            row.currency,
            row.posting_date,
            row.company,
        )
    result = []
    for year in reversed(years):
        values = [round(monthly_map.get((year, month_no), 0)) for month_no in range(1, 13)]
        result.append({"year": year, "values": values})

    return result


def get_current_month_sales_summary() -> dict[str, float]:
    start_date, end_date = get_reference_month_range()

    invoice_totals = frappe.db.sql(
        """
        SELECT
            posting_date,
            currency,
            company,
            SUM(COALESCE(net_total, 0)) AS sales_amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND COALESCE(is_return, 0) = 0
          AND posting_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY posting_date, currency, company
        """,
        {"start_date": start_date, "end_date": end_date},
        as_dict=True,
    )

    item_totals = frappe.db.sql(
        """
        SELECT
            si.posting_date,
            si.company,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0)) AS sales_kg,
            SUM(COALESCE(sii.stock_qty, sii.qty, 0) * COALESCE(sii.incoming_rate, 0)) AS total_cost
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND COALESCE(si.is_return, 0) = 0
          AND si.posting_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY si.posting_date, si.company
        """,
        {"start_date": start_date, "end_date": end_date},
        as_dict=True,
    )

    money_balances = frappe.db.sql(
        """
        SELECT
            acc.account_type,
            gle.posting_date,
            gle.company,
            SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS balance
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.is_cancelled = 0
          AND acc.is_group = 0
          AND acc.account_type IN ('Cash', 'Bank')
        GROUP BY acc.account_type, gle.posting_date, gle.company
        """,
        as_dict=True,
    )

    collections = frappe.db.sql(
        """
        SELECT
            posting_date,
            company,
            SUM(
                COALESCE(base_received_amount, 0) + CASE
                    WHEN COALESCE(base_received_amount, 0) = 0 THEN COALESCE(base_paid_amount, 0)
                    ELSE 0
                END
            ) AS collections_total
        FROM `tabPayment Entry`
        WHERE docstatus = 1
          AND payment_type = 'Receive'
          AND posting_date BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY posting_date, company
        """,
        {"start_date": start_date, "end_date": end_date},
        as_dict=True,
    )

    balances = {"Cash": 0.0, "Bank": 0.0}
    for row in money_balances:
        balances[row.account_type] = balances.get(row.account_type, 0) + convert_company_currency_amount(
            row.balance,
            row.posting_date,
            row.company,
        )

    sales_kg = sum(flt(row.sales_kg) for row in item_totals)
    sales_amount = sum(
        convert_to_reporting_currency(row.sales_amount, row.currency, row.posting_date, row.company)
        for row in invoice_totals
    )
    total_cost = sum(
        convert_company_currency_amount(row.total_cost, row.posting_date, row.company)
        for row in item_totals
    )
    collections_total = sum(
        convert_company_currency_amount(row.collections_total, row.posting_date, row.company)
        for row in collections
    )
    debtor_amount = get_debtor_total()

    return {
        "sales_amount": sales_amount,
        "sales_kg": sales_kg,
        "cash_total": flt(balances.get("Cash")),
        "bank_total": flt(balances.get("Bank")),
        "collections_total": collections_total,
        "debtor_total": debtor_amount,
        "avg_price": sales_amount / sales_kg if sales_kg else 0,
        "avg_cost": total_cost / sales_kg if sales_kg else 0,
        "balance_total": debtor_amount,
    }


def get_sales_amount_timeline(year_limit: int = 2) -> dict[str, list[Any]]:
    labels = []
    values = []

    for row in get_monthly_sales_amount(year_limit=year_limit):
        for month_name, month_value in zip(MONTH_LABELS, row["values"]):
            labels.append(f"{month_name}\n{row['year']}")
            values.append(month_value)

    return {"labels": labels, "values": values}


def get_customer_balances(limit: int | None = None) -> list[dict[str, Any]]:
    limit = cint(limit)
    result = [
        frappe._dict(client=party_label, customer=party_label, balance=balance)
        for party_label, balance in get_debtor_balance_rows().items()
    ]
    result.sort(key=lambda row: row["balance"], reverse=True)
    return result[:limit] if limit else result


def get_latest_dashboard_update() -> str:
    latest_posting_date = frappe.db.sql(
        """
        SELECT MAX(posting_date) AS latest_posting_date
        FROM `tabSales Invoice`
        WHERE docstatus = 1
        """,
        as_dict=True,
    )[0].latest_posting_date

    if latest_posting_date:
        return format_datetime(latest_posting_date, "dd.MM.yyyy")

    return format_datetime(now_datetime(), "dd.MM.yyyy HH:mm")
