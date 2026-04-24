"""
Kunlik Balans Hisoboti — Balance Sheet (point-in-time snapshot).

Tanlangan sana (report_date) bo'yicha 4 ta snapshot ustun:
  • [sana-3]  o'sha sana oxiridagi balans
  • [sana-2]
  • [sana-1]
  • [sana]   (bugun)

Oldingi oyga tegadigan snapshot ustunlar ko'rsatilmaydi
(oyning 1-3 kunlarida 1-3 ustun, 4-kundan boshlab 4 ustun).

Tree:
  Asset  →  account hierarchy  →  leaf accounts
  Liability
  Equity

Drilldown leaf accountlarda:
  • account_type = Receivable / Payable  →  party breakdown
  • account_type = Stock                 →  item group breakdown (SLE orqali)
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days, get_first_day
from collections import defaultdict


# ─── Entry point ──────────────────────────────────────────────────────────────

def execute(filters=None):
	filters = filters or {}
	_validate(filters)
	periods = _get_periods(filters)
	columns = _get_columns(periods)
	data    = _get_data(filters, periods)
	return columns, data


def _validate(filters):
	if not filters.get("report_date"):
		frappe.throw(_("Sana majburiy"))


# ─── Periods (point-in-time snapshots) ────────────────────────────────────────

def _get_periods(filters):
	rd          = getdate(filters["report_date"])
	month_start = get_first_day(rd)
	periods     = []
	for offset, key in ((-3, "p_d3"), (-2, "p_d2"), (-1, "p_d1"), (0, "p_d0")):
		d = add_days(rd, offset)
		if d >= month_start:
			periods.append({
				"key":      key,
				"label":    d.strftime("%d.%m.%Y"),
				"snapshot": str(d),
			})
	return periods


# ─── Columns ──────────────────────────────────────────────────────────────────

def _get_columns(periods):
	cols = [{"label": _("Ko'rsatkich"), "fieldname": "label",
	         "fieldtype": "Data", "width": 360}]
	for p in periods:
		cols.append({"label": p["label"], "fieldname": p["key"],
		             "fieldtype": "Currency", "width": 140})
	return cols


# ─── Main ─────────────────────────────────────────────────────────────────────

def _get_data(filters, periods):
	currency = filters.get("currency") or "USD"
	company  = filters.get("company")  or frappe.defaults.get_user_default("Company")

	accounts = _fetch_accounts(company)

	gl_snap       = {p["key"]: _fetch_gl_balances(company, currency, p["snapshot"])    for p in periods}
	party_snap    = {p["key"]: _fetch_party_balances(company, currency, p["snapshot"]) for p in periods}
	stock_ig_snap = {p["key"]: _fetch_stock_ig_balances(p["snapshot"])                 for p in periods}

	# Pre-compute group totals via lft/rgt (rollup from leaves)
	group_totals = {p["key"]: _rollup_group_totals(accounts, gl_snap[p["key"]]) for p in periods}

	rows = []
	for root_type, root_label in (("Asset",     _("Aktiv")),
	                              ("Liability", _("Passiv")),
	                              ("Equity",    _("Kapital"))):
		tree_accs = [a for a in accounts if a["root_type"] == root_type]
		if not tree_accs:
			continue

		rows += _build_tree_rows(tree_accs, gl_snap, group_totals, party_snap,
		                         stock_ig_snap, periods, company, root_type)

		total_bal = {p["key"]: _root_total(tree_accs, gl_snap[p["key"]], root_type) for p in periods}
		rows.append(_make_row(_("Jami {0}").format(root_label), 0, total_bal, periods,
		                      is_total=1, bold=1))
		rows.append(_empty_row(periods))

	return rows


# ─── Account fetch & tree helpers ─────────────────────────────────────────────

def _fetch_accounts(company):
	return frappe.db.sql("""
		SELECT name, account_name, account_number, parent_account,
		       is_group, root_type, account_type, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND root_type IN ('Asset', 'Liability', 'Equity')
		  AND disabled = 0
		ORDER BY lft
	""", [company], as_dict=True)


def _rollup_group_totals(accounts, gl_balances):
	"""
	For every group account, sum leaf balances inside [lft, rgt].
	Returns {account_name: summed_balance}.
	"""
	leaves = [(a["lft"], flt(gl_balances.get(a["name"], 0)))
	          for a in accounts if not a["is_group"]]
	totals = {}
	for a in accounts:
		if not a["is_group"]:
			totals[a["name"]] = flt(gl_balances.get(a["name"], 0))
			continue
		s = 0.0
		for lft, bal in leaves:
			if a["lft"] < lft < a["rgt"]:
				s += bal
		totals[a["name"]] = s
	return totals


def _root_total(tree_accs, gl_balances, root_type):
	total = sum(flt(gl_balances.get(a["name"], 0))
	            for a in tree_accs if not a["is_group"])
	return _sign(total, root_type)


def _sign(balance, root_type):
	"""Liability and Equity are natural credit balances — flip sign for display."""
	return balance if root_type == "Asset" else -balance


def _build_tree_rows(tree_accs, gl_snap, group_totals, party_snap,
                     stock_ig_snap, periods, company, root_type):
	by_parent = defaultdict(list)
	for a in tree_accs:
		by_parent[a["parent_account"]].append(a)

	rows = []

	def emit(account, indent):
		is_group = bool(account["is_group"])
		per_vals = {}
		for p in periods:
			key = p["key"]
			raw = group_totals[key][account["name"]] if is_group else flt(gl_snap[key].get(account["name"], 0))
			per_vals[key] = _sign(raw, root_type)

		label = _short(account["name"], company)
		rows.append(_make_row(label, indent, per_vals, periods, bold=1 if is_group else 0))

		if not is_group:
			atype = account.get("account_type") or ""
			if atype in ("Receivable", "Payable"):
				rows.extend(_party_rows(account["name"], party_snap, periods, root_type, indent + 1))
			elif atype == "Stock":
				rows.extend(_stock_ig_rows(account["name"], stock_ig_snap, periods, root_type, indent + 1))

		for child in sorted(by_parent.get(account["name"], []), key=lambda x: x["lft"]):
			emit(child, indent + 1)

	for root in sorted(by_parent.get(None, []), key=lambda x: x["lft"]):
		emit(root, 0)

	return rows


def _party_rows(account_name, party_snap, periods, root_type, indent):
	party_keys = set()
	for p in periods:
		for pr in party_snap[p["key"]].get(account_name, []):
			party_keys.add((pr["party_type"], pr["party"]))

	if not party_keys:
		return []

	party_names = {pk: _party_display_name(pk[0], pk[1]) for pk in party_keys}

	rows = []
	for pk in sorted(party_keys, key=lambda x: party_names[x] or ""):
		per_vals = {}
		for p in periods:
			raw = 0.0
			for pr in party_snap[p["key"]].get(account_name, []):
				if (pr["party_type"], pr["party"]) == pk:
					raw = flt(pr["balance"])
					break
			per_vals[p["key"]] = _sign(raw, root_type)
		if not any(flt(v) for v in per_vals.values()):
			continue
		rows.append(_make_row(party_names[pk] or pk[1], indent, per_vals, periods))
	return rows


def _stock_ig_rows(account_name, stock_ig_snap, periods, root_type, indent):
	ig_keys = set()
	for p in periods:
		ig_keys.update(stock_ig_snap[p["key"]].get(account_name, {}).keys())

	if not ig_keys:
		return []

	rows = []
	for ig in sorted(ig_keys):
		per_vals = {}
		for p in periods:
			raw = flt(stock_ig_snap[p["key"]].get(account_name, {}).get(ig, 0))
			per_vals[p["key"]] = _sign(raw, root_type)
		if not any(flt(v) for v in per_vals.values()):
			continue
		rows.append(_make_row(ig, indent, per_vals, periods))
	return rows


# ─── GL / party / stock fetchers ──────────────────────────────────────────────

def _fetch_gl_balances(company, currency, snapshot_date):
	rows = frappe.db.sql("""
		SELECT account,
		       SUM(debit_in_account_currency - credit_in_account_currency) AS balance
		FROM `tabGL Entry`
		WHERE is_cancelled     = 0
		  AND account_currency = %s
		  AND company          = %s
		  AND posting_date     <= %s
		GROUP BY account
	""", [currency, company, snapshot_date], as_dict=True)
	return {r.account: flt(r.balance) for r in rows}


def _fetch_party_balances(company, currency, snapshot_date):
	rows = frappe.db.sql("""
		SELECT account, party_type, party,
		       SUM(debit_in_account_currency - credit_in_account_currency) AS balance
		FROM `tabGL Entry`
		WHERE is_cancelled     = 0
		  AND account_currency = %s
		  AND company          = %s
		  AND posting_date     <= %s
		  AND party IS NOT NULL AND party != ''
		GROUP BY account, party_type, party
	""", [currency, company, snapshot_date], as_dict=True)
	result = defaultdict(list)
	for r in rows:
		result[r.account].append({
			"party_type": r.party_type,
			"party":      r.party,
			"balance":    flt(r.balance),
		})
	return dict(result)


def _fetch_stock_ig_balances(snapshot_date):
	"""
	Returns {stock_account: {item_group: cumulative_value}}
	Cumulative SLE stock_value_difference up to snapshot_date.
	"""
	rows = frappe.db.sql("""
		SELECT w.account AS stock_account,
		       COALESCE(NULLIF(i.item_group, ''), %s) AS item_group,
		       SUM(sle.stock_value_difference) AS balance
		FROM `tabStock Ledger Entry` sle
		JOIN `tabItem`      i ON i.name = sle.item_code
		JOIN `tabWarehouse` w ON w.name = sle.warehouse
		WHERE sle.is_cancelled = 0
		  AND sle.posting_date <= %s
		  AND w.account IS NOT NULL
		GROUP BY w.account, i.item_group
	""", [_("Kategoriyasiz"), snapshot_date], as_dict=True)
	result = defaultdict(dict)
	for r in rows:
		result[r.stock_account][r.item_group] = flt(r.balance)
	return dict(result)


# ─── Display helpers ──────────────────────────────────────────────────────────

def _short(account_name, company):
	suffix = f" - {company}"
	if account_name and account_name.endswith(suffix):
		return account_name[: -len(suffix)]
	return account_name or ""


def _party_display_name(party_type, party):
	field = {"Customer":  "customer_name",
	         "Supplier":  "supplier_name",
	         "Employee":  "employee_name",
	         "Shareholder": "title"}.get(party_type)
	if field:
		return frappe.db.get_value(party_type, party, field) or party
	return party


def _make_row(label, indent, period_dict, periods, bold=0, is_total=0):
	row = {
		"label":     label,
		"indent":    indent,
		"bold":      bold,
		"is_total":  is_total,
	}
	for p in periods:
		row[p["key"]] = flt(period_dict.get(p["key"], 0))
	return row


def _empty_row(periods):
	row = {"label": "", "indent": 0, "bold": 0, "is_total": 0}
	for p in periods:
		row[p["key"]] = None
	return row
