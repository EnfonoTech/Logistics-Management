"""Warehouse management for a freight forwarder.

HSM store other people's cargo between two legs of a shipment. Nothing here belongs
to HSM, so none of it is an Item and none of it touches the Stock Ledger -- the unit
of record is the waybill and the unit of measure is CBM. See wms/README.md.
"""
