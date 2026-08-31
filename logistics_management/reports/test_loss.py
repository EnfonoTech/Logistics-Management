# Copyright (c) 2026, siva and contributors
# See license.txt
"""Tests for the Profit and Loss Statement override.

These cover the two defects that reached production: the report raising a
TypeError on periods with no expense accounts, and the Gross Profit row
reporting only the last period's figure in its Total column.

They exercise the pure functions directly, so no fixtures or company setup is
needed and they cannot touch real financial data.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from logistics_management.reports.loss import (
	COGS_ACCOUNT,
	DIRECT_EXPENSES_ACCOUNT,
	get_gross_profit,
	insert_gross_profit_under_stock_expenses,
)


def _periods(*keys):
	return [frappe._dict({"key": k}) for k in keys]


def _income(**by_key):
	# get_data() returns [...accounts, total_row, blank_row]; the report reads [-2].
	return [frappe._dict({"account_name": "Sales"}), frappe._dict(by_key), frappe._dict({})]


def _expense_with_direct(**by_key):
	row = frappe._dict({"account_name": DIRECT_EXPENSES_ACCOUNT})
	row.update(by_key)
	return [row, frappe._dict({"account_name": "Total Expense"}), frappe._dict({})]


class TestProfitAndLossOverride(FrappeTestCase):
	def test_insert_gross_profit_tolerates_no_expense_rows(self):
		"""ERPNext's get_data() returns None for a period with no matching accounts.

		The report used to iterate that None and 500 on out-of-range date filters.
		"""
		gross_profit = {"account_name": "Gross Profit"}

		self.assertEqual(insert_gross_profit_under_stock_expenses(None, gross_profit), [])
		self.assertEqual(insert_gross_profit_under_stock_expenses([], gross_profit), [])

	def test_gross_profit_row_is_inserted_under_cogs(self):
		gross_profit = {"account_name": "Gross Profit"}
		expense = [
			frappe._dict({"account_name": COGS_ACCOUNT, "indent": 1}),
			frappe._dict({"account_name": "Administrative Expenses", "indent": 1}),
		]

		result = insert_gross_profit_under_stock_expenses(expense, gross_profit)

		self.assertEqual(len(result), 3)
		self.assertEqual(result[1]["account_name"], "Gross Profit")
		self.assertEqual(result[1]["indent"], 2)

	def test_gross_profit_total_is_the_sum_of_every_period(self):
		"""The Total column must sum the periods, not hold the last one.

		This is the defect that reported a Total of 0.00 against roughly
		QAR 912k of actual gross profit whenever the last month was empty.
		"""
		period_list = _periods("jan", "feb", "mar")
		income = _income(jan=100.0, feb=200.0, mar=0.0)
		expense = _expense_with_direct(jan=40.0, feb=50.0, mar=0.0)

		gross_profit = get_gross_profit(income, expense, period_list, None, currency="QAR")

		self.assertIsNotNone(gross_profit)
		self.assertEqual(gross_profit["jan"], 60.0)
		self.assertEqual(gross_profit["feb"], 150.0)
		self.assertEqual(gross_profit["mar"], 0.0)
		self.assertEqual(gross_profit["total"], 210.0)

	def test_a_period_without_direct_expenses_does_not_inherit_the_previous_one(self):
		"""total_income / direct_expense used to be initialised outside the loop."""
		period_list = _periods("jan", "feb")
		income = _income(jan=100.0, feb=100.0)
		# Only January carries a Direct Expenses figure.
		expense = _expense_with_direct(jan=40.0)

		gross_profit = get_gross_profit(income, expense, period_list, None, currency="QAR")

		self.assertEqual(gross_profit["jan"], 60.0)
		# February has no direct expense, so gross profit is the full income.
		self.assertEqual(gross_profit["feb"], 100.0)
		self.assertEqual(gross_profit["total"], 160.0)

	def test_returns_none_when_every_period_is_zero(self):
		period_list = _periods("jan", "feb")
		income = _income(jan=0.0, feb=0.0)
		expense = _expense_with_direct(jan=0.0, feb=0.0)

		self.assertIsNone(get_gross_profit(income, expense, period_list, None, currency="QAR"))
