from frappe.utils import flt
import frappe

def execute(filters=None):
    columns, data, chart = [], [], None

    columns = [
        {"label": "Job Details", "fieldname": "job_details", "fieldtype": "Link", "options": "Job Details", "width": 200},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "Sales Person", "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 150},
        {"label": "Sales Invoices", "fieldname": "sales_invoices", "fieldtype": "Data", "width": 270},
        {"label": "Total Credit", "fieldname": "total_credit", "fieldtype": "Currency", "width": 150},
        {"label": "Total Debit", "fieldname": "total_debit", "fieldtype": "Currency", "width": 150},
        {"label": "Profit & Loss", "fieldname": "profit_and_loss", "fieldtype": "Currency", "width": 150},
    ]

    job_details_filter = filters.get('job_details') if filters else None
    sales_person_filter = filters.get('sales_person') if filters else None
    from_date = filters.get('from_date') if filters else None
    to_date = filters.get('to_date') if filters else None

    # Check for user permissions
    user_permissions = frappe.permissions.get_user_permissions(frappe.session.user)
    user_company = user_permissions.get('Company', [None])[0]

    job_details_filters = {}
    if user_company:
        job_details_filters['company'] = user_company.doc
    if job_details_filter:
        job_details_filters['name'] = ['in', job_details_filter]
    if sales_person_filter:
        job_details_filters['sales_person'] = ['in', sales_person_filter]
    if from_date and to_date:
        job_details_filters['date'] = ['between', [from_date, to_date]]  

    job_details_list = frappe.get_all('Job Details', filters=job_details_filters, fields=['name', 'sales_person', 'job_id'])

    overall_credit_total = 0
    overall_debit_total = 0
    overall_profit_and_loss = 0

    has_data = False
    invoice_data = []
    pnl_data = []
    pnl_colors = []
    debit_data = []

    for job in job_details_list:
        total_credit = 0
        total_debit = 0
        customer = job.job_id
        sales_invoices_list = []

        # Fetch and process Sales Invoices
        sales_invoices_filters = {'custom_job_number': job.name, 'docstatus': 1}

        sales_invoices = frappe.get_all('Sales Invoice', filters=sales_invoices_filters, fields=['name', 'base_grand_total'])
        if sales_invoices:
            has_data = True
            sales_invoices_list = [inv.name for inv in sales_invoices]

        for inv in sales_invoices:
            total_credit += flt(inv.base_grand_total)

        # Fetch and process Purchase Invoices
        purchase_invoices_filters = {'custom_job_number': job.name, 'docstatus': 1}

        purchase_invoices = frappe.get_all('Purchase Invoice', filters=purchase_invoices_filters, fields=['name', 'base_grand_total'])
        if purchase_invoices:
            has_data = True
        for inv in purchase_invoices:
            total_debit += flt(inv.base_grand_total)

        # Fetch and process Journal Entries (only debit items)
        journal_entries_filters = {'custom_job_number': job.name, 'docstatus': 1}

        journal_entries = frappe.get_all('Journal Entry', filters=journal_entries_filters, fields=['name'])
        if journal_entries:
            has_data = True
        for entry in journal_entries:
            entries = frappe.get_all('Journal Entry Account', filters={'parent': entry.name, 'debit': ['>', 0]}, fields=['account', 'debit'])
            for je in entries:
                total_debit += flt(je.debit)

        # Calculate profit and loss
        if has_data:
            profit_and_loss = total_credit - total_debit
            overall_profit_and_loss += profit_and_loss

            # Append totals for each job
            data.append({
                'job_details': job.name,
                'customer': customer,
                'sales_person': job.sales_person,
                'sales_invoices': ', '.join(sales_invoices_list),
                'total_credit': total_credit,
                'total_debit': total_debit,
                'profit_and_loss': profit_and_loss
            })

            overall_credit_total += total_credit
            overall_debit_total += total_debit

            invoice_data.append({
                'x': job.name,
                'y': total_credit
            })
            debit_data.append({
                'x': job.name,
                'y': total_debit
            })
            pnl_data.append({
                'x': job.name,
                'y': profit_and_loss
            })
            pnl_colors.append('red' if profit_and_loss < 0 else 'green')

    if not has_data:
        frappe.msgprint("No data found for the selected period")

    # Append overall totals if data is present
    if has_data:
        data.append({
            'job_details': 'Overall Totals',
            'customer': '',
            'sales_person': '',
            'sales_invoices': '',
            'total_credit': overall_credit_total,
            'total_debit': overall_debit_total,
            'profit_and_loss': overall_profit_and_loss
        })

    # Prepare chart configuration if filters are applied
    if sales_person_filter or job_details_filter:
        chart = {
            "data": {
                "labels": [d['x'] for d in invoice_data],
                "datasets": [
                    {
                        "name": "Total Credit",
                        "values": [d['y'] for d in invoice_data]
                    },
                    {
                        "name": "Total Debit",
                        "values": [d['y'] for d in debit_data]
                    },
                    {
                        "name": "Profit & Loss",
                        "values": [d['y'] for d in pnl_data]
                    }
                ]
            },
            "type": "bar",
            "colors": [
                "#7cd6fd",  # Color for Total Credit
                "#743ee2",  # Color for Total Debit
                pnl_colors   # Dynamic color list for Profit & Loss
            ]
        }

    return columns, data, None, chart
