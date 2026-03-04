"""
Davriy PnL Hisoboti — Profit & Loss (Daily / Weekly / Monthly)

All monetary amounts come from GL Entry (account_currency = target currency).
Item-group breakdown uses proportional distribution via SI Items / SLE.

Tree structure:
  0  4000-Income  |  5100-Direct Exp  |  [sep]  |  Gross Profit  |  Indirect Exp  |  Net Profit
  1  4100 parent  |  5110 parent      |          |  by item_group |  accounts
  2  4110 leaf    |  5111-COGS        |
  3  item groups  |  item groups      |
                  |  5119-StockAdj    |
                  |  item groups      |
"""

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, add_days, add_months, get_first_day, get_last_day
from collections import defaultdict


# ─── Entry point ──────────────────────────────────────────────────────────────

def execute(filters=None):
	filters = filters or {}
	_validate(filters)
	periods   = _get_periods(filters)
	columns   = _get_columns(periods)
	data      = _get_data(filters, periods)
	return columns, data


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Dan va Gacha sanalari majburiy"))
	if getdate(filters["from_date"]) > getdate(filters["to_date"]):
		frappe.throw(_("'Dan' sanasi 'Gacha' sanasidan katta bo'lmasligi kerak"))


# ─── Period generation ────────────────────────────────────────────────────────

def _get_periods(filters):
	from_date = getdate(filters["from_date"])
	to_date   = getdate(filters["to_date"])
	ptype     = filters.get("period", "Monthly")
	if ptype == "Daily":   return _daily_periods(from_date, to_date)
	if ptype == "Weekly":  return _weekly_periods(from_date, to_date)
	return _monthly_periods(from_date, to_date)


def _monthly_periods(from_date, to_date):
	periods, cursor = [], get_first_day(from_date)
	while cursor <= to_date:
		p_end = min(get_last_day(cursor), to_date)
		periods.append({"key": cursor.strftime("m_%Y_%m"), "label": cursor.strftime("%b %Y"),
		                "from_date": str(max(cursor, from_date)), "to_date": str(p_end)})
		cursor = get_first_day(add_months(cursor, 1))
	return periods


def _weekly_periods(from_date, to_date):
	periods, cursor, week = [], from_date, 1
	while cursor <= to_date:
		p_end = min(add_days(cursor, 6), to_date)
		periods.append({"key": f"w_{week:02d}",
		                "label": f"Hafta {week} ({cursor.strftime('%d.%m')}-{p_end.strftime('%d.%m')})",
		                "from_date": str(cursor), "to_date": str(p_end)})
		cursor = add_days(p_end, 1); week += 1
	return periods


def _daily_periods(from_date, to_date):
	periods, cursor = [], from_date
	while cursor <= to_date:
		periods.append({"key": cursor.strftime("d_%Y_%m_%d"), "label": cursor.strftime("%d.%m.%Y"),
		                "from_date": str(cursor), "to_date": str(cursor)})
		cursor = add_days(cursor, 1)
	return periods


# ─── Columns ──────────────────────────────────────────────────────────────────

def _get_columns(periods):
	cols = [{"label": _("Ko'rsatkich"), "fieldname": "label", "fieldtype": "Data", "width": 320}]
	for p in periods:
		cols.append({"label": p["label"], "fieldname": p["key"], "fieldtype": "Currency", "width": 130})
	cols.append({"label": _("Jami"), "fieldname": "total", "fieldtype": "Currency", "width": 160})
	return cols


# ─── Main ─────────────────────────────────────────────────────────────────────

def _get_data(filters, periods):
	currency    = filters.get("currency") or "USD"
	company     = filters.get("company") or frappe.defaults.get_user_default("Company")
	accumulated = cint(filters.get("accumulated_values"))

	base_params = {
		"currency":  currency,
		"company":   company,
		"from_date": filters["from_date"],
		"to_date":   filters["to_date"],
		"na":        _("Kategoriyasiz"),
	}

	# ── Fetch GL amounts + distribute to item groups ───────────────────────────
	income_nested = _fetch_income(base_params)        # {account: {ig: [{date,amt}]}}
	cogs_ig_raw   = _fetch_cogs_by_ig(base_params)    # [{date, grp, amount}]
	s_adj_ig_raw  = _fetch_stock_adj_by_ig(base_params)
	indir_raw     = _fetch_indirect(base_params)

	# ── Pivot to {grp: {period_key: amount}} ──────────────────────────────────
	cogs_ig   = _pivot_groups(cogs_ig_raw,  periods)
	s_adj_ig  = _pivot_groups(s_adj_ig_raw, periods)
	indir_acc = _pivot_groups(indir_raw,    periods)

	# Pivot income: {account: {ig: {period_key: amount}}}
	income_pivoted = {
		acc: _pivot_groups(ig_rows, periods)
		for acc, ig_rows in income_nested.items()
	}

	# ── Optional accumulated (running totals) ──────────────────────────────────
	if accumulated:
		income_pivoted = {
			acc: {ig: _accumulate(pd, periods) for ig, pd in ig_dict.items()}
			for acc, ig_dict in income_pivoted.items()
		}
		cogs_ig   = {ig: _accumulate(pd, periods) for ig, pd in cogs_ig.items()}
		s_adj_ig  = {ig: _accumulate(pd, periods) for ig, pd in s_adj_ig.items()}
		indir_acc = {ig: _accumulate(pd, periods) for ig, pd in indir_acc.items()}

	# ── Aggregate income across accounts for Gross Profit calc ────────────────
	rev_by_ig = {}
	for ig_dict in income_pivoted.values():
		for ig, pd in ig_dict.items():
			rev_by_ig[ig] = _add(rev_by_ig.get(ig, {}), pd)

	rev_tot     = _sum_groups(rev_by_ig)
	cogs_tot    = _sum_groups(cogs_ig)
	s_adj_tot   = _sum_groups(s_adj_ig)
	direct_tot  = _add(cogs_tot, s_adj_tot)
	indir_tot   = _sum_groups(indir_acc)

	# Gross Profit = Income (4000) − Direct Expenses (5100 = 5111 + 5119)
	all_igs     = set(rev_by_ig) | set(cogs_ig) | set(s_adj_ig)
	gross_ig    = {
		ig: _subtract(rev_by_ig.get(ig, {}), _add(cogs_ig.get(ig, {}), s_adj_ig.get(ig, {})))
		for ig in all_igs
	}
	gross_ig    = {ig: pd for ig, pd in gross_ig.items() if any(flt(v) for v in pd.values())}
	gross_tot   = _subtract(rev_tot, direct_tot)
	net_profit  = _subtract(gross_tot, indir_tot)

	# ── Account labels ─────────────────────────────────────────────────────────
	lbl = {n: _acc_label(n, company) for n in ("4000", "5100", "5110", "5111", "5119")}

	# ── Build rows ─────────────────────────────────────────────────────────────
	rows = []

	# ── Income (account hierarchy: 4000 → parent → leaf → items) ─────────────
	rows += _build_income_rows(income_pivoted, rev_tot, lbl["4000"], company, periods)
	rows.append(_empty(periods))

	# ── Direct Expenses ───────────────────────────────────────────────────────
	rows.append(_row(lbl["5100"], 0, direct_tot, periods, bold=1))
	rows.append(_row(lbl["5110"], 1, direct_tot, periods, bold=1))
	if cogs_tot:
		rows.append(_row(lbl["5111"], 2, cogs_tot, periods, bold=1))
		for ig, pd in sorted(cogs_ig.items()):
			rows.append(_row(ig, 3, pd, periods))
	if s_adj_tot:
		rows.append(_row(lbl["5119"], 2, s_adj_tot, periods, bold=1))
		for ig, pd in sorted(s_adj_ig.items()):
			rows.append(_row(ig, 3, pd, periods))
	rows.append(_empty(periods))

	# ── Gross Profit ──────────────────────────────────────────────────────────
	rows.append(_row(_("Yalpi foyda (Gross Profit)"), 0, gross_tot, periods,
	                 bold=1, is_profit_row=1, is_separator=1))
	for ig, pd in sorted(gross_ig.items()):
		rows.append(_row(ig, 1, pd, periods, is_profit_row=1))
	rows.append(_pct_row(_("Yalpi foyda, %"), 0, gross_tot, rev_tot, periods))

	# ── Indirect Expenses ─────────────────────────────────────────────────────
	rows.append(_row(_("Bilvosita xarajatlar (Indirect Expenses)"), 0, indir_tot, periods, bold=1))
	for acc, pd in sorted(indir_acc.items()):
		rows.append(_row(_short(acc, company), 1, pd, periods))

	# ── Net Profit ────────────────────────────────────────────────────────────
	rows.append(_row(_("Sof foyda (Net Profit)"), 0, net_profit, periods,
	                 bold=1, is_profit_row=1, is_separator=1))
	rows.append(_pct_row(_("Sof foyda, %"), 0, net_profit, rev_tot, periods))

	return rows


# ─── Income hierarchy builder ─────────────────────────────────────────────────

def _build_income_rows(income_pivoted, rev_tot, root_label, company, periods):
	"""
	income_pivoted: {account_name: {ig: {period_key: amount}}}
	Builds:  root(0) → parent_acc(1) → leaf_acc(2) → item_groups(3)
	"""
	if not income_pivoted:
		return [_row(root_label, 0, {}, periods, bold=1)]

	rows = [_row(root_label, 0, rev_tot, periods, bold=1)]

	# Load account info (account_name, parent_account) in one query
	accs = list(income_pivoted.keys())
	acc_meta = {r.name: r for r in frappe.db.get_all(
		"Account", filters={"name": ("in", accs)},
		fields=["name", "parent_account"]
	)}

	# Group leaf accounts by their immediate parent
	by_parent = defaultdict(list)
	for acc in sorted(accs):
		parent = (acc_meta.get(acc) or frappe._dict()).parent_account
		by_parent[parent or "__root__"].append(acc)

	for parent, children in sorted(by_parent.items()):
		# Parent aggregate
		p_ig = {}
		for child in children:
			for ig, pd in income_pivoted.get(child, {}).items():
				p_ig[ig] = _add(p_ig.get(ig, {}), pd)
		p_tot = _sum_groups(p_ig)

		if parent != "__root__":
			rows.append(_row(_short(parent, company), 1, p_tot, periods, bold=1))
			leaf_indent = 2
		else:
			leaf_indent = 1

		for child in sorted(children):
			c_ig    = income_pivoted.get(child, {})
			c_tot   = _sum_groups(c_ig)
			rows.append(_row(_short(child, company), leaf_indent, c_tot, periods))
			for ig, pd in sorted(c_ig.items()):
				rows.append(_row(ig, leaf_indent + 1, pd, periods))

	return rows


# ─── Data fetchers ────────────────────────────────────────────────────────────

def _fetch_income(params):
	"""
	GL Entry credits on Income accounts (account_currency = target).
	Distributes each voucher's GL amount to item groups via SI Items.
	Returns: {account: [{posting_date, grp, amount}]}
	"""
	gl_rows = frappe.db.sql("""
		SELECT
			ge.posting_date,
			ge.account,
			ge.voucher_type,
			ge.voucher_no,
			SUM(ge.credit_in_account_currency - ge.debit_in_account_currency) AS amount
		FROM `tabGL Entry` ge
		JOIN `tabAccount` acc ON acc.name = ge.account
		WHERE ge.is_cancelled      = 0
		  AND ge.is_opening        != 'Yes'
		  AND ge.voucher_type      != 'Period Closing Voucher'
		  AND (ge.finance_book IS NULL OR ge.finance_book = '')
		  AND ge.account_currency  = %(currency)s
		  AND acc.root_type        = 'Income'
		  AND acc.is_group         = 0
		  AND (%(company)s IS NULL OR ge.company = %(company)s)
		  AND ge.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ge.posting_date, ge.account, ge.voucher_type, ge.voucher_no
		HAVING amount != 0
	""", params, as_dict=True)

	if not gl_rows:
		return {}

	# Bulk-fetch SI item distributions
	si_vouchers = {r.voucher_no for r in gl_rows if r.voucher_type == "Sales Invoice"}
	si_dist     = _si_item_dist(si_vouchers, params["na"])

	result = defaultdict(list)
	for r in gl_rows:
		dist = si_dist.get(r.voucher_no) if r.voucher_type == "Sales Invoice" else None
		for row in _distribute(r.posting_date, flt(r.amount), dist, params["na"]):
			result[r.account].append(row)

	return dict(result)


def _fetch_cogs_by_ig(params):
	"""
	GL Entry debits on Cost of Goods Sold accounts.
	Distributes to item groups via SLE.
	Returns: [{posting_date, grp, amount}]
	"""
	gl_rows = frappe.db.sql("""
		SELECT
			ge.posting_date,
			ge.voucher_type,
			ge.voucher_no,
			SUM(ge.debit_in_account_currency - ge.credit_in_account_currency) AS amount
		FROM `tabGL Entry` ge
		JOIN `tabAccount` acc ON acc.name = ge.account
		WHERE ge.is_cancelled      = 0
		  AND ge.is_opening        != 'Yes'
		  AND ge.voucher_type      != 'Period Closing Voucher'
		  AND (ge.finance_book IS NULL OR ge.finance_book = '')
		  AND ge.account_currency  = %(currency)s
		  AND acc.account_type     = 'Cost of Goods Sold'
		  AND acc.is_group         = 0
		  AND (%(company)s IS NULL OR ge.company = %(company)s)
		  AND ge.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ge.posting_date, ge.voucher_type, ge.voucher_no
		HAVING amount != 0
	""", params, as_dict=True)

	return _gl_to_ig_via_sle(gl_rows, params["na"])


def _fetch_stock_adj_by_ig(params):
	"""
	GL Entry debits on account_number='5119' (Stock Adjustment).
	Distributes to item groups via SLE.
	Returns: [{posting_date, grp, amount}]
	"""
	# Find stock adjustment account(s) by account_number
	adj_accs = frappe.db.get_all(
		"Account",
		filters={"account_number": "5119", "company": params["company"]},
		pluck="name",
	)
	if not adj_accs:
		# Fallback: account_type = 'Stock Adjustment'
		adj_accs = frappe.db.get_all(
			"Account",
			filters={"account_type": "Stock Adjustment", "company": params["company"]},
			pluck="name",
		)
	if not adj_accs:
		return []

	ph = ", ".join(["%s"] * len(adj_accs))
	values = (
		[params["currency"]]
		+ list(adj_accs)
		+ [params["company"], params["company"], params["from_date"], params["to_date"]]
	)
	gl_rows = frappe.db.sql(f"""
		SELECT
			ge.posting_date,
			ge.voucher_type,
			ge.voucher_no,
			SUM(ge.debit_in_account_currency - ge.credit_in_account_currency) AS amount
		FROM `tabGL Entry` ge
		WHERE ge.is_cancelled     = 0
		  AND ge.is_opening       != 'Yes'
		  AND ge.voucher_type     != 'Period Closing Voucher'
		  AND (ge.finance_book IS NULL OR ge.finance_book = '')
		  AND ge.account_currency = %s
		  AND ge.account IN ({ph})
		  AND (%s IS NULL OR ge.company = %s)
		  AND ge.posting_date BETWEEN %s AND %s
		GROUP BY ge.posting_date, ge.voucher_type, ge.voucher_no
		HAVING amount != 0
	""", values, as_dict=True)

	return _gl_to_ig_via_sle(gl_rows, params["na"])


def _fetch_indirect(params):
	"""
	Non-stock expense GL entries in target currency.
	Returns: [{posting_date, grp (=account), amount}]
	"""
	_skip = ("Cost of Goods Sold", "Stock", "Fixed Asset", "Depreciation",
	         "Capital Work in Progress", "Stock Received But Not Billed", "Stock Adjustment")
	skip_sql = ", ".join(f"'{t}'" for t in _skip)
	return frappe.db.sql(f"""
		SELECT
			ge.posting_date,
			ge.account                                            AS grp,
			SUM(ge.debit_in_account_currency
			    - ge.credit_in_account_currency)                  AS amount
		FROM `tabGL Entry` ge
		JOIN `tabAccount` acc ON acc.name = ge.account
		WHERE ge.is_cancelled     = 0
		  AND ge.is_opening       != 'Yes'
		  AND ge.voucher_type     != 'Period Closing Voucher'
		  AND (ge.finance_book IS NULL OR ge.finance_book = '')
		  AND ge.account_currency = %(currency)s
		  AND acc.root_type       = 'Expense'
		  AND acc.is_group        = 0
		  AND acc.account_type NOT IN ({skip_sql})
		  AND (%(company)s IS NULL OR ge.company = %(company)s)
		  AND ge.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ge.posting_date, ge.account
		HAVING amount != 0
	""", params, as_dict=True)


# ─── Item-group distribution helpers ─────────────────────────────────────────

def _gl_to_ig_via_sle(gl_rows, na_label):
	"""Convert GL rows → [{posting_date, grp, amount}] using SLE item proportions."""
	if not gl_rows:
		return []
	voucher_nos = {r.voucher_no for r in gl_rows}
	sle_dist    = _sle_item_dist(voucher_nos, na_label)
	result = []
	for r in gl_rows:
		dist = sle_dist.get(r.voucher_no)
		result += _distribute(r.posting_date, flt(r.amount), dist, na_label)
	return result


def _distribute(posting_date, total_amount, dist, na_label):
	"""
	Proportionally split total_amount across item groups.
	dist: [{item_group, weight}] or None
	"""
	if not dist or not total_amount:
		return [{"posting_date": posting_date, "grp": na_label, "amount": total_amount}]
	total_w = sum(flt(d["weight"]) for d in dist)
	if not total_w:
		return [{"posting_date": posting_date, "grp": na_label, "amount": total_amount}]
	return [
		{"posting_date": posting_date,
		 "grp":          d["item_group"],
		 "amount":       total_amount * flt(d["weight"]) / total_w}
		for d in dist
	]


def _si_item_dist(si_names, na_label):
	"""Bulk fetch SI item group weights. Returns {si_name: [{item_group, weight}]}"""
	if not si_names:
		return {}
	ph   = ", ".join(["%s"] * len(si_names))
	rows = frappe.db.sql(f"""
		SELECT sii.parent, COALESCE(NULLIF(i.item_group, ''), %s) AS item_group,
		       SUM(sii.net_amount) AS weight
		FROM  `tabSales Invoice Item` sii
		JOIN  `tabItem` i ON i.name = sii.item_code
		WHERE sii.parent IN ({ph})
		GROUP BY sii.parent, i.item_group
	""", [na_label] + list(si_names), as_dict=True)
	result = defaultdict(list)
	for r in rows:
		result[r.parent].append({"item_group": r.item_group, "weight": flt(r.weight)})
	return dict(result)


def _sle_item_dist(voucher_nos, na_label):
	"""Bulk fetch SLE item group weights. Returns {voucher_no: [{item_group, weight}]}"""
	if not voucher_nos:
		return {}
	ph   = ", ".join(["%s"] * len(voucher_nos))
	rows = frappe.db.sql(f"""
		SELECT sle.voucher_no, COALESCE(NULLIF(i.item_group, ''), %s) AS item_group,
		       SUM(ABS(sle.stock_value_difference)) AS weight
		FROM  `tabStock Ledger Entry` sle
		JOIN  `tabItem` i ON i.name = sle.item_code
		WHERE sle.voucher_no IN ({ph}) AND sle.is_cancelled = 0
		  AND sle.stock_value_difference != 0
		GROUP BY sle.voucher_no, i.item_group
	""", [na_label] + list(voucher_nos), as_dict=True)
	result = defaultdict(list)
	for r in rows:
		result[r.voucher_no].append({"item_group": r.item_group, "weight": flt(r.weight)})
	return dict(result)


# ─── Pivoting & math ──────────────────────────────────────────────────────────

def _pivot_groups(flat_rows, periods):
	"""[{posting_date, grp, amount}] → {grp: {period_key: amount}}"""
	bounds = [(p["key"], getdate(p["from_date"]), getdate(p["to_date"])) for p in periods]
	res    = defaultdict(lambda: defaultdict(float))
	for r in flat_rows:
		d = getdate(r["posting_date"])
		for key, fd, td in bounds:
			if fd <= d <= td:
				res[r["grp"]][key] += flt(r["amount"])
				break
	return {g: dict(pd) for g, pd in res.items() if any(pd.values())}


def _accumulate(period_dict, periods):
	result, running = {}, 0.0
	for p in periods:
		running        += flt(period_dict.get(p["key"], 0))
		result[p["key"]] = running
	return result


def _sum_groups(g):
	tot = defaultdict(float)
	for pd in g.values():
		for k, v in pd.items():
			tot[k] += flt(v)
	return dict(tot)


def _add(d1, d2):
	res = dict(d1)
	for k, v in d2.items():
		res[k] = flt(res.get(k, 0)) + flt(v)
	return res


def _subtract(d1, d2):
	res = dict(d1)
	for k, v in d2.items():
		res[k] = flt(res.get(k, 0)) - flt(v)
	for k in d2:
		if k not in res:
			res[k] = -flt(d2[k])
	return res


# ─── Account label helpers ────────────────────────────────────────────────────

def _acc_label(account_number, company):
	name = frappe.db.get_value("Account",
		{"account_number": account_number, "company": company}, "name")
	return _short(name, company) if name else account_number


def _short(account_name, company):
	suffix = f" - {company}"
	if account_name and account_name.endswith(suffix):
		return account_name[: -len(suffix)]
	return account_name or ""


# ─── Row builders ─────────────────────────────────────────────────────────────

def _row(label, indent, period_dict, periods, bold=0, is_profit_row=0, is_separator=0):
	row = {"label": label, "indent": indent, "bold": bold,
	       "is_profit_row": is_profit_row, "is_separator": is_separator, "is_pct_row": 0}
	total = 0.0
	for p in periods:
		v = flt(period_dict.get(p["key"], 0))
		row[p["key"]] = v
		total += v
	row["total"] = total
	return row


def _pct_row(label, indent, numerator_dict, denominator_dict, periods):
	row = {"label": label, "indent": indent, "bold": 1,
	       "is_profit_row": 1, "is_separator": 0, "is_pct_row": 1}
	total_num = sum(flt(numerator_dict.get(p["key"],   0)) for p in periods)
	total_den = sum(flt(denominator_dict.get(p["key"], 0)) for p in periods)
	for p in periods:
		num = flt(numerator_dict.get(p["key"],   0))
		den = flt(denominator_dict.get(p["key"], 0))
		row[p["key"]] = round(num / den * 100, 2) if den else 0.0
	row["total"] = round(total_num / total_den * 100, 2) if total_den else 0.0
	return row


def _empty(periods):
	row = {"label": "", "indent": 0, "bold": 0,
	       "is_profit_row": 0, "is_separator": 0, "is_pct_row": 0, "total": None}
	for p in periods:
		row[p["key"]] = None
	return row
