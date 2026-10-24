"""Sequential numeric codes (10001, 10002 … / 101, 102 …) as required by the client spec."""

import frappe
from frappe.utils import cint


def next_numeric_name(doctype: str, start: int) -> str:
	"""Return the next free numeric name for `doctype`, never lower than `start`.

	Only purely numeric names are considered, so manually renamed records do not
	break the sequence. Written for MariaDB (the Frappe default).
	"""
	last = frappe.db.sql(
		f"""select max(cast(name as unsigned)) from `tab{doctype}`
		where name regexp '^[0-9]+$' for update"""
	)[0][0]
	return str(max(cint(last) + 1, start))


def start_autoincrement_at(doctype: str, start: int) -> None:
	"""Make the next autoincrement name of `doctype` at least `start` (e.g. Product ID 201)."""
	from frappe.database.sequence import set_next_val

	last = frappe.db.sql(f"select max(name) from `tab{doctype}`")[0][0]
	set_next_val(doctype, max(cint(last), start - 1), is_val_used=True)
