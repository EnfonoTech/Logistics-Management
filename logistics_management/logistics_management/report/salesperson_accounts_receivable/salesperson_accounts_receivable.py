# Copyright (c) 2024, siva and contributors
# For license information, please see license.txt

# logistics_management/api/report.py

import frappe

def execute(filters=None):
    from_date = filters.get('from_date') if filters else None
    to_date = filters.get('to_date') if filters else frappe.utils.today()
    customer = filters.get('customer') if filters else None

    # Build the base SQL query with filtering based on submitted status
    query = """
        SELECT
            si.customer AS customer,
            si.name AS invoice_name,
            si.posting_date AS posting_date,
            si.base_grand_total AS invoiced_amount,
            si.total_advance AS paid_amount,
            si.outstanding_amount AS outstanding_amount
        FROM
            `tabSales Invoice` si
        WHERE
            si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
    """
    
    # Add customer filter if provided
    if customer:
        query += " AND si.customer = %s"
        data = frappe.db.sql(query, (from_date, to_date, customer), as_dict=True)
    else:
        data = frappe.db.sql(query, (from_date, to_date), as_dict=True)

    columns = [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "Invoice Name", "fieldname": "invoice_name", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 150},
        {"label": "Invoiced Amount", "fieldname": "invoiced_amount", "fieldtype": "Currency", "width": 150},
        {"label": "Paid Amount", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 150},
        {"label": "Outstanding Amount", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 170}
    ]
    
    return columns, data
