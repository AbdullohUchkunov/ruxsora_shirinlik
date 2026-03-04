import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days, add_months, get_first_day, get_last_day


def execute(filters=None):
	filters = filters or {}
	validate_filters(filters)
	periods = get_periods(filters)
	columns = get_columns(filters, periods)
	data = get_data(filters, periods)
	return columns, data


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Dan va Gacha sanalari majburiy"))
	if not filters.get("party_type"):
		frappe.throw(_("Kontragent turi majburiy"))
	if getdate(filters["from_date"]) > getdate(filters["to_date"]):
		frappe.throw(_("'Dan' sanasi 'Gacha' sanasidan kichik bo'lishi kerak"))


# ─── Period generation ────────────────────────────────────────────────────────

def get_periods(filters):
	"""
	Returns list of dicts: [{key, label, from_date, to_date}, ...]
	key is used as fieldname prefix (e.g. "2025_12" or "w_01")
	"""
	from_date = getdate(filters["from_date"])
	to_date = getdate(filters["to_date"])
	period_type = filters.get("period", "Monthly")

	if period_type == "Monthly":
		return _monthly_periods(from_date, to_date)
	return _weekly_periods(from_date, to_date)


def _monthly_periods(from_date, to_date):
	periods = []
	cursor = get_first_day(from_date)
	while cursor <= to_date:
		p_start = max(cursor, from_date)
		p_end = min(get_last_day(cursor), to_date)
		periods.append({
			"key": cursor.strftime("m_%Y_%m"),
			"label": cursor.strftime("%b %Y"),
			"from_date": str(p_start),
			"to_date": str(p_end),
		})
		cursor = get_first_day(add_months(cursor, 1))
	return periods


def _weekly_periods(from_date, to_date):
	periods = []
	cursor = from_date
	week = 1
	while cursor <= to_date:
		p_end = min(add_days(cursor, 6), to_date)
		periods.append({
			"key": f"w_{week:02d}",
			"label": f"Hafta {week} ({cursor.strftime('%d.%m')}-{p_end.strftime('%d.%m')})",
			"from_date": str(cursor),
			"to_date": str(p_end),
		})
		cursor = add_days(p_end, 1)
		week += 1
	return periods


# ─── Columns ──────────────────────────────────────────────────────────────────

def get_columns(filters, periods):
	party_type = filters.get("party_type", "Party")
	cols = [
		{"label": _(party_type), "fieldname": "party", "fieldtype": "Data", "width": 220},
		{"label": _("Boshlang'ich Debet"), "fieldname": "opening_debit", "fieldtype": "Currency", "width": 150},
		{"label": _("Boshlang'ich Kredit"), "fieldname": "opening_credit", "fieldtype": "Currency", "width": 150},
	]
	for p in periods:
		cols.append({"label": f"{p['label']} Debet", "fieldname": f"{p['key']}_debit", "fieldtype": "Currency", "width": 130})
		cols.append({"label": f"{p['label']} Kredit", "fieldname": f"{p['key']}_credit", "fieldtype": "Currency", "width": 130})
	cols += [
		{"label": _("Joriy Debet"), "fieldname": "closing_debit", "fieldtype": "Currency", "width": 150},
		{"label": _("Joriy Kredit"), "fieldname": "closing_credit", "fieldtype": "Currency", "width": 150},
	]
	return cols


# ─── Data ─────────────────────────────────────────────────────────────────────

def get_data(filters, periods):
	party_type = filters["party_type"]
	party_filter = filters.get("party")
	currency = filters.get("currency") or "UZS"
	from_date = filters["from_date"]

	parties = _get_party_list(party_type, party_filter, currency)
	if not parties:
		return []

	party_names = [p["party"] for p in parties]

	# Single bulk query for opening balance (before from_date)
	opening_map = _fetch_bulk(party_type, party_names, None, from_date, currency, before=True)

	# Single bulk query per period
	period_maps = {
		p["key"]: _fetch_bulk(party_type, party_names, p["from_date"], p["to_date"], currency)
		for p in periods
	}

	# Totals accumulator
	totals = {f: 0.0 for f in ["opening_debit", "opening_credit", "closing_debit", "closing_credit"]}
	for p in periods:
		totals[f"{p['key']}_debit"] = 0.0
		totals[f"{p['key']}_credit"] = 0.0

	rows = []
	for party in party_names:
		opening = opening_map.get(party, {"debit": 0.0, "credit": 0.0})
		opening_net = flt(opening["credit"]) - flt(opening["debit"])

		row = {
			"party": party,
			"opening_debit": opening["debit"],
			"opening_credit": opening["credit"],
		}

		running_net = opening_net
		for p in periods:
			pd = period_maps[p["key"]].get(party, {"debit": 0.0, "credit": 0.0})
			row[f"{p['key']}_debit"] = pd["debit"]
			row[f"{p['key']}_credit"] = pd["credit"]
			running_net += flt(pd["credit"]) - flt(pd["debit"])

		row["closing_credit"] = running_net if running_net > 0 else 0.0
		row["closing_debit"] = abs(running_net) if running_net < 0 else 0.0

		for key in totals:
			totals[key] += flt(row.get(key, 0))

		rows.append(row)

	# Total row at top
	total_row = {"party": _("JAMI"), **totals, "bold": 1}
	return [total_row] + rows


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_party_list(party_type, party=None, currency=None):
	"""Return distinct parties that have GL entries for the given currency."""
	conditions = [
		"party_type = %(party_type)s",
		"party IS NOT NULL AND party != ''",
		"is_cancelled = 0",
		"account_currency = %(currency)s",
	]
	values = {"party_type": party_type, "currency": currency or "UZS"}

	if party:
		conditions.append("party = %(party)s")
		values["party"] = party

	where = " AND ".join(conditions)
	return frappe.db.sql(
		f"SELECT DISTINCT party FROM `tabGL Entry` WHERE {where} ORDER BY party",
		values, as_dict=True
	)


def _fetch_bulk(party_type, party_list, from_date, to_date, currency, before=False):
	"""
	Fetch net debit/credit for a list of parties in one SQL query.
	Returns: {party: {"debit": x, "credit": y}}

	Net logic:
	  gross_credit - gross_debit > 0  →  credit position
	  gross_credit - gross_debit < 0  →  debit position
	"""
	if not party_list:
		return {}

	placeholders = ", ".join(["%s"] * len(party_list))
	base_args = [party_type] + list(party_list)

	if before:
		date_clause = "AND posting_date < %s"
		date_args = [to_date]
	else:
		date_clause = "AND posting_date >= %s AND posting_date <= %s"
		date_args = [from_date, to_date]

	rows = frappe.db.sql(f"""
		SELECT
			party,
			IFNULL(SUM(debit_in_account_currency), 0)  AS gross_debit,
			IFNULL(SUM(credit_in_account_currency), 0) AS gross_credit
		FROM `tabGL Entry`
		WHERE party_type = %s
		  AND party IN ({placeholders})
		  {date_clause}
		  AND account_currency = %s
		  AND is_cancelled = 0
		GROUP BY party
	""", tuple(base_args + date_args + [currency]), as_dict=True)

	result = {}
	for row in rows:
		net = flt(row.gross_credit) - flt(row.gross_debit)
		result[row.party] = {
			"credit": net if net > 0 else 0.0,
			"debit": abs(net) if net < 0 else 0.0,
		}
	return result
