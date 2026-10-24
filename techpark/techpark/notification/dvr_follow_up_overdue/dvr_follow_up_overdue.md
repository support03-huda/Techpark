Your follow-up for **{{ doc.customer_name }}** ({{ doc.plant_name }}) was due **yesterday, {{ frappe.utils.formatdate(doc.next_action_date) }}** and is still open.

**Next action:** {{ doc.next_action }}

From visit {{ doc.name }} on {{ frappe.utils.formatdate(doc.visit_date) }} ({{ doc.visit_purpose }}). Close the To Do once it is done.
