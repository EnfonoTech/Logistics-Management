import frappe
from frappe.utils import flt

def execute(filters=None):
    columns, data = [], []

    # Define columns
    columns = [
        {"label": "Job Details", "fieldname": "job_details", "fieldtype": "Link", "options": "Job Details", "width": 125},
        {"label": "Invoice Type", "fieldname": "invoice_type", "fieldtype": "Data", "width": 135},
        {"label": "Invoice ID", "fieldname": "invoice_id", "fieldtype": "Dynamic Link", "options": "invoice_type", "width": 195},
        {"label": "Item", "fieldname": "item", "fieldtype": "Data", "width": 175},
        {"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 150},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 150},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 150},
        {"label": "Profit & Loss", "fieldname": "profit_and_loss", "fieldtype": "Currency", "width": 150},
    ]

    # Check for user permissions
    user_permissions = frappe.permissions.get_user_permissions(frappe.session.user)
    user_company = user_permissions.get('Company', [None])[0]

    # Apply company filter to Job Details if user has a company restriction
    job_details_filter = filters.get('job_details') if filters else None
    job_details_conditions = {}

    if user_company:
        job_details_conditions['company'] = user_company.doc

    if job_details_filter:
        job_details_conditions['name'] = ['in', job_details_filter]

    job_details_list = frappe.get_all('Job Details', filters=job_details_conditions, fields=['name'])

    overall_credit_total = 0
    overall_debit_total = 0
    overall_sales_outstanding_total = 0
    overall_purchase_outstanding_total = 0
    overall_profit_and_loss = 0

    for job in job_details_list:
        total_credit = 0
        total_debit = 0
        total_sales_outstanding = 0
        total_purchase_outstanding = 0

        # Fetch and process Sales Invoices
        sales_invoices = frappe.get_all('Sales Invoice', filters={'custom_job_number': job.name, 'docstatus': 1}, fields=['name', 'base_grand_total', 'outstanding_amount'])
        for inv in sales_invoices:
            items = frappe.get_all('Sales Invoice Item', filters={'parent': inv.name}, fields=['item_code', 'qty', 'rate', 'amount'])
            for item in items:
                data.append({
                    'job_details': job.name,
                    'invoice_type': 'Sales Invoice',
                    'invoice_id': inv.name,
                    'item': item.item_code,
                    'quantity': item.qty,
                    'rate': item.rate,
                    'amount': item.amount,
                    'credit': flt(item.amount),
                    'debit': 0,
                    'sales_outstanding_amount': flt(inv.outstanding_amount),
                    'purchase_outstanding_amount': 0,
                    'profit_and_loss': ''
                })
            total_credit += flt(inv.base_grand_total)
            total_sales_outstanding += flt(inv.outstanding_amount)

        # Fetch and process Purchase Invoices
        purchase_invoices = frappe.get_all('Purchase Invoice', filters={'custom_job_number': job.name, 'docstatus': 1}, fields=['name', 'base_grand_total', 'outstanding_amount'])
        for inv in purchase_invoices:
            items = frappe.get_all('Purchase Invoice Item', filters={'parent': inv.name}, fields=['item_code', 'qty', 'rate', 'amount'])
            for item in items:
                data.append({
                    'job_details': job.name,
                    'invoice_type': 'Purchase Invoice',
                    'invoice_id': inv.name,
                    'item': item.item_code,
                    'quantity': item.qty,
                    'rate': item.rate,
                    'amount': item.amount,
                    'credit': 0,
                    'debit': flt(item.amount),
                    'sales_outstanding_amount': 0,
                    'purchase_outstanding_amount': flt(inv.outstanding_amount),
                    'profit_and_loss': ''
                })
            total_debit += flt(inv.base_grand_total)
            total_purchase_outstanding += flt(inv.outstanding_amount)

        # Fetch and process Journal Entries (only debit items)
        journal_entries = frappe.get_all('Journal Entry', filters={'custom_job_number': job.name, 'docstatus': 1}, fields=['name'])
        for entry in journal_entries:
            entries = frappe.get_all('Journal Entry Account', filters={'parent': entry.name, 'debit': ['>', 0]}, fields=['account', 'debit'])
            for je in entries:
                data.append({
                    'job_details': job.name,
                    'invoice_type': 'Journal Entry',
                    'invoice_id': entry.name,
                    'item': je.account,
                    'quantity': '',
                    'rate': '',
                    'amount': je.debit,
                    'credit': 0,
                    'debit': flt(je.debit),
                    'sales_outstanding_amount': '',
                    'purchase_outstanding_amount': '',
                    'profit_and_loss': ''
                })
                total_debit += flt(je.debit)

        # Calculate profit and loss
        profit_and_loss = total_credit - total_debit
        overall_profit_and_loss += profit_and_loss

        # Append totals for each job
        data.append({
            'job_details': job.name,
            'invoice_type': '<b>Totals</b>',
            'invoice_id': '',
            'item': '',
            'quantity': '',
            'rate': '',
            'amount': '',
            'credit': total_credit,
            'debit': total_debit,
            'sales_outstanding_amount': total_sales_outstanding,
            'purchase_outstanding_amount': total_purchase_outstanding,
            'profit_and_loss': profit_and_loss
        })

        overall_credit_total += total_credit
        overall_debit_total += total_debit
        overall_sales_outstanding_total += total_sales_outstanding
        overall_purchase_outstanding_total += total_purchase_outstanding

    # Append overall totals
    data.append({
        'job_details': '',
        'invoice_type': '<b>Overall Totals</b>',
        'invoice_id': '',
        'item': '',
        'quantity': '',
        'rate': '',
        'amount': '',
        'credit': overall_credit_total,
        'debit': overall_debit_total,
        'sales_outstanding_amount': overall_sales_outstanding_total,
        'purchase_outstanding_amount': overall_purchase_outstanding_total,
        'profit_and_loss': overall_profit_and_loss
    })

    return columns, data
