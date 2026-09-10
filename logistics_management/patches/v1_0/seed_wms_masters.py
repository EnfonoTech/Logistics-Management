"""Seed the package types and cargo classes on an existing site.

The same function runs from after_install for fresh sites -- see wms/setup.py for why
both are needed.
"""

from logistics_management.wms.setup import seed_masters


def execute():
	seed_masters()
