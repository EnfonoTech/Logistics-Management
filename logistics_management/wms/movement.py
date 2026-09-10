"""Arrival at the destination, and delivery to each customer.

Arrival is per container: one job arrives, and that is the event that takes space in the
receiving warehouse. Delivery is per waybill, because HSM ring each customer separately
and each one takes their cargo on its own day. HSM raised the arrival step themselves --
"in Qatar there is an option to receive it, I don't think that has come in this".
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from logistics_management.wms import capacity

STATUS_IN_WAREHOUSE = "In Warehouse"
STATUS_IN_MOVEMENT = "In Movement"
STATUS_ARRIVED = "Arrived at Destination"
STATUS_DELIVERED = "Delivered"


@frappe.whitelist()
def confirm_arrival(job, arrival_date=None, received_by=None, destination_warehouse=None):
	"""Confirm a console job reached its destination warehouse.

	This is the only thing that consumes space at the destination, and it must happen
	exactly once -- the wms_arrival_confirmed flag is the guard, checked under a lock.
	"""
	frappe.has_permission("Job Details", "write", doc=job, throw=True)

	row = frappe.db.get_value(
		"Job Details",
		job,
		["name", "wms_arrival_confirmed", "wms_destination_warehouse", "job_type"],
		as_dict=True,
		for_update=True,
	)
	if not row:
		frappe.throw(_("Job {0} does not exist").format(job))
	if row.wms_arrival_confirmed:
		frappe.throw(_("Arrival has already been confirmed for job {0}.").format(job))

	destination = destination_warehouse or row.wms_destination_warehouse
	if not destination:
		frappe.throw(_("Set a destination warehouse on job {0} before confirming arrival.").format(job))

	receipts = frappe.get_all(
		"Receipt Note",
		filters={"wms_job": job, "docstatus": 1},
		fields=["name", "total_cbm", "wms_status", "wms_waybill_console"],
	)
	if not receipts:
		frappe.throw(_("Job {0} has no Receipt Notes linked to it.").format(job))

	not_moving = sorted(r.name for r in receipts if r.wms_status != STATUS_IN_MOVEMENT)
	if not_moving:
		frappe.throw(
			_("These Receipt Notes are not in movement, so they cannot arrive: {0}").format(
				", ".join(not_moving)
			)
		)

	arrival_date = getdate(arrival_date or nowdate())
	total_cbm = sum(flt(r.total_cbm) for r in receipts)

	capacity.consume(destination, total_cbm, context=_("arrival of job {0}").format(job))

	frappe.db.set_value(
		"Job Details",
		job,
		{
			"wms_arrival_confirmed": 1,
			"wms_arrival_date": arrival_date,
			"wms_received_by": received_by or frappe.session.user,
			"wms_destination_warehouse": destination,
		},
		update_modified=False,
	)

	for r in receipts:
		frappe.db.set_value(
			"Receipt Note",
			r.name,
			{
				"wms_status": STATUS_ARRIVED,
				"wms_arrival_date": arrival_date,
				"current_warehouse_unit": destination,
			},
			update_modified=False,
		)
		if r.wms_waybill_console:
			frappe.db.set_value(
				"Waybill Console", r.wms_waybill_console, "wms_status", STATUS_ARRIVED,
				update_modified=False,
			)

	return frappe._dict(job=job, destination=destination, cbm=total_cbm, receipts=len(receipts))


@frappe.whitelist()
def record_delivery(waybill_console, delivery_date=None, delivery_mode=None, collected_by=None,
                    create_pod=True):
	"""Deliver one waybill to its customer and free the space it occupied.

	Refuses before arrival is confirmed: HSM cannot hand over cargo the destination
	warehouse has not acknowledged receiving.
	"""
	frappe.has_permission("Waybill Console", "write", doc=waybill_console, throw=True)

	console = frappe.db.get_value(
		"Waybill Console",
		waybill_console,
		["name", "waybill_no", "customer", "job_details", "wms_status", "wms_receipt_note",
		 "wms_delivered"],
		as_dict=True,
		for_update=True,
	)
	if not console:
		frappe.throw(_("Waybill Console {0} does not exist").format(waybill_console))
	if console.wms_delivered:
		frappe.throw(_("Waybill {0} has already been delivered.").format(console.waybill_no))
	if console.wms_status != STATUS_ARRIVED:
		frappe.throw(
			_("Waybill {0} is {1}. Confirm arrival at the destination warehouse before delivering it.")
			.format(console.waybill_no, console.wms_status or _("not in movement")),
			title=_("Not Yet Arrived"),
		)

	delivery_date = getdate(delivery_date or nowdate())
	receipt = None
	if console.wms_receipt_note:
		receipt = frappe.db.get_value(
			"Receipt Note", console.wms_receipt_note,
			["name", "total_cbm", "current_warehouse_unit"], as_dict=True,
		)

	if receipt and receipt.current_warehouse_unit:
		capacity.release(
			receipt.current_warehouse_unit, receipt.total_cbm,
			context=_("delivery of waybill {0}").format(console.waybill_no),
		)

	frappe.db.set_value(
		"Waybill Console",
		waybill_console,
		{
			"wms_status": STATUS_DELIVERED,
			"wms_delivered": 1,
			"wms_delivery_date": delivery_date,
			"delivery_mode": delivery_mode or "Delivery",
			"wms_collected_by": collected_by or "",
		},
		update_modified=False,
	)

	if receipt:
		frappe.db.set_value(
			"Receipt Note",
			receipt.name,
			{
				"wms_status": STATUS_DELIVERED,
				"wms_delivery_date": delivery_date,
				"current_warehouse_unit": None,
			},
			update_modified=False,
		)

	pod = None
	if cint(create_pod):
		pod = make_pod(waybill_console, delivery_date=delivery_date, collected_by=collected_by)

	return frappe._dict(waybill_console=waybill_console, pod=pod, delivery_date=delivery_date)


def make_pod(waybill_console, delivery_date=None, collected_by=None):
	"""Create the POD for a delivered waybill, prefilled from the console and its job.

	The blank print of this is what the driver takes to the customer; the signed scan
	comes back onto the same record via signed_pod.
	"""
	existing = frappe.db.exists("POD", {"waybill_console": waybill_console})
	if existing:
		return existing

	console = frappe.get_doc("Waybill Console", waybill_console)
	job = frappe.get_doc("Job Details", console.job_details) if console.job_details else None

	pod = frappe.new_doc("POD")
	pod.waybill_console = console.name
	pod.customer_name = console.customer
	pod.shipper_name = console.shipper
	pod.number_of_packages = console.no_of_packages
	pod.date = getdate(delivery_date or nowdate())
	pod.collected_by = collected_by or ""
	pod.wms_delivered_at = frappe.utils.now()

	if job:
		pod.job_details = job.name
		pod.company = job.company
		pod.mode_of_transport = job.mode_of_transport
		pod.container_no = job.container_no
		pod.mbl_number = job.mbl_number
		pod.hbl_number = job.hbl_number
		pod.mawbl_number = job.mawbl_number
		pod.hawbl_number = job.hawbl_number
		pod.delivery_location = job.wms_destination_warehouse or job.place_of_delivery
		pod.loading_location = job.wms_origin_warehouse or job.place_of_receipt
	else:
		pod.company = frappe.defaults.get_user_default("Company")

	pod.insert()
	return pod.name


@frappe.whitelist()
def get_deliverable_waybills(job):
	"""Waybills on a job that have arrived and are not yet delivered."""
	frappe.has_permission("Waybill Console", "read", throw=True)
	return frappe.get_all(
		"Waybill Console",
		filters={"job_details": job, "wms_status": STATUS_ARRIVED, "wms_delivered": 0},
		fields=["name", "waybill_no", "customer", "no_of_packages", "volume"],
		order_by="waybill_no",
	)
