// Copyright (c) 2026, Techpark International

frappe.query_reports["Principal-wise Customers"] = {
	filters: [
		{ fieldname: "principal", label: __("Principal"), fieldtype: "Link", options: "Principal" },
		{
			fieldname: "customer_status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nProspect\nActive Customer\nInactive",
		},
		{ fieldname: "territory_region", label: __("Region"), fieldtype: "Link", options: "Territory Region" },
		{ fieldname: "zone", label: __("Zone"), fieldtype: "Select", options: "\nNorth\nSouth\nEast\nWest\nCentral" },
	],
};
