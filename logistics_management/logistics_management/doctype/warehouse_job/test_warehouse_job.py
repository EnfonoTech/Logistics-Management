# Copyright (c) 2026, siva and Contributors
# See license.txt
"""Guards on create_warehouse_job_from_receipts.

It is a public HTTP endpoint that mutates stored warehouse capacity, so the
idempotency and consistency checks are the thing worth testing.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from logistics_management.logistics_management.doctype.warehouse_job.warehouse_job import (
	create_warehouse_job_from_receipts,
)


class TestWarehouseJob(FrappeTestCase):
	def test_empty_selection_is_rejected(self):
		self.assertRaises(frappe.ValidationError, create_warehouse_job_from_receipts, [])
		self.assertRaises(frappe.ValidationError, create_warehouse_job_from_receipts, "[]")

	def test_unknown_receipt_note_is_rejected(self):
		self.assertRaises(
			frappe.ValidationError,
			create_warehouse_job_from_receipts,
			["_TEST-RN-DOES-NOT-EXIST"],
		)
