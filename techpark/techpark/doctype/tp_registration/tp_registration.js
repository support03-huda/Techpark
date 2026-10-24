// Copyright (c) 2026, Techpark International
// Approve (role + existing employee) and Reject buttons for approvers.

frappe.ui.form.on("TP Registration", {
	refresh(frm) {
		const onload = frm.doc.__onload || {};
		if (frm.doc.status !== "Pending" || !onload.can_decide) return;

		frm.add_custom_button(__("Approve"), () => approve_registration(frm)).addClass("btn-primary");
		frm.add_custom_button(__("Reject"), () => reject_registration(frm));
	},
});

function approve_registration(frm) {
	const onload = frm.doc.__onload || {};
	const employees = onload.employees || [];
	const employee_options = [{ label: "", value: "" }].concat(
		employees.map((e) => ({
			label: [e.employee_name, e.name, e.designation].filter(Boolean).join(" · "),
			value: e.name,
		}))
	);
	const matched = onload.matched_employee;

	frappe.prompt(
		[
			{
				fieldname: "role",
				fieldtype: "Select",
				label: __("Role"),
				options: (onload.role_choices || ["Sales User"]).join("\n"),
				default: "Sales User",
				reqd: 1,
				description: __("Sales User: own visits only. Sales Manager: all records. Admin: also approves registrations."),
			},
			{
				fieldname: "existing_employee",
				fieldtype: "Check",
				label: __("Existing Employee"),
				default: matched ? 1 : 0,
			},
			{
				fieldname: "employee",
				fieldtype: "Select",
				label: __("Employee"),
				options: employee_options,
				default: matched || "",
				depends_on: "existing_employee",
				mandatory_depends_on: "existing_employee",
				description: matched
					? __("Found by email. Change it only if this is someone else.")
					: __("Active employees that have no login yet."),
			},
		],
		(values) => {
			frm.call("approve", {
				role: values.role,
				existing_employee: values.existing_employee,
				employee: values.existing_employee ? values.employee : null,
			}).then((r) => {
				const mail_sent = r.message && r.message.mail_sent;
				frappe.show_alert(
					{
						message: mail_sent
							? __("Approved. An email to set the password was sent to {0}.", [frappe.utils.escape_html(frm.doc.email)])
							: __("Approved, but no email could be sent: the site has no outgoing email account. Set the password on the user (User > Password > Set Password) and tell the person."),
						indicator: mail_sent ? "green" : "orange",
					},
					15
				);
				frm.reload_doc();
			});
		},
		__("Approve Registration"),
		__("Approve")
	);
}

function reject_registration(frm) {
	frappe.prompt(
		[{ fieldname: "remarks", fieldtype: "Small Text", label: __("Reason (optional)") }],
		(values) => {
			frm.call("reject", { remarks: values.remarks || null }).then((r) => {
				const mail_sent = r.message && r.message.mail_sent;
				frappe.show_alert(
					{
						message: mail_sent
							? __("Registration rejected. {0} has been informed by email.", [frappe.utils.escape_html(frm.doc.email)])
							: __("Registration rejected, but no email could be sent."),
						indicator: "orange",
					},
					10
				);
				frm.reload_doc();
			});
		},
		__("Reject Registration"),
		__("Reject")
	);
}
