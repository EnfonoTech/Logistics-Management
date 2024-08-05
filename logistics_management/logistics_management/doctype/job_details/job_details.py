import frappe
from frappe.model.document import Document

class JobDetails(Document):
    def before_save(self):
        if self.company == 'HARBOUR SHIPPING AND MARINE SERVICES WLL-NVOCC DIVISSION':
            job_numbers = frappe.get_all('Job Details', filters={'name': ['like', 'HSMN%']}, fields=['name'], order_by='cast(substr(name, 5) as unsigned) ASC')
            job_numbers = [int(job['name'][4:]) for job in job_numbers]
            
            next_job_number = 1001  
            for number in job_numbers:
                if number != next_job_number:
                    break
                next_job_number += 1

            next_job_number_formatted = 'HSMN{:04}'.format(next_job_number)
            self.name = next_job_number_formatted


    # def get_options(self):
    #     # Fetch naming series options from the doctype
    #     options = frappe.get_meta('Job Details').get_field('naming_series').options
    #     return options.split('\n')

    # def get_next_naming_series_value(self):
    #     last_doc = frappe.get_all('Job Details', filters={'naming_series': self.naming_series}, fields=['name'], order_by='cast(substr(name, length(naming_series) + 1) as unsigned) DESC', limit_page_length=1)
    #     last_value = last_doc[0].get('name')[len(self.naming_series):] if last_doc else None

    #     next_value = int(last_value) + 1 if last_value is not None else 1
    #     next_value_formatted = '{}{:05}'.format(self.naming_series, next_value)

    #     return next_value_formatted

@frappe.whitelist()
def generate_project(docname):
    if not docname:
        frappe.msgprint("Document name is required to generate the waybill.")
        return

    doc = frappe.get_doc("Job Details", docname)

    if doc.project:
        frappe.throw(f"Project already exists for this Job: {doc.project}")
    else:
        # Check if the naming series needs to be set for SecOnd Company
        if doc.company == 'SecOnd Company':
            doc.before_save()  # Ensure naming series logic is applied

        data = frappe.get_doc({
            "doctype": "Project",
            "project_name": doc.name,
            "custom_job_details": doc.name,
        })
        data.insert(ignore_permissions=True)
        frappe.msgprint(f"Project generated successfully: {data.name}")

        doc.project = data.name
        doc.save(ignore_permissions=True)

        return doc.project
