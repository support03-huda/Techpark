Your follow-up for **{{ doc.customer_name }}** ({{ doc.plant_name }}) is due **tomorrow, {{ frappe.utils.formatdate(doc.next_action_date) }}**.

**Next action:** {{ doc.next_action }}

From visit {{ doc.name }} on {{ frappe.utils.formatdate(doc.visit_date) }} ({{ doc.visit_purpose }}).
