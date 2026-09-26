# Techpark — Customer Master (styled like the TP prototype)

## What's in this package

```
techpark/                                  -> copy into apps/techpark/techpark/
├── naming.py                              numeric auto-naming (Customer 10001+, Plant 101+)
├── api/customer_master.py                 whitelisted server API used by the page
└── techpark/                              the "Techpark" module folder
    ├── doctype/tp_customer/               TP Customer doctype (+ form & list JS) — named "TP Customer" so it does not clash with ERPNext's Customer
    ├── doctype/customer_agent/            child table: "Handled by agents"
    ├── doctype/plant/                     Plant master doctype
    └── page/customer_master/              Desk page /app/customer-master (JS + CSS)
```

## Install

1. Copy the contents of this `techpark/` folder into `frappe-bench/apps/techpark/techpark/`
   (merge; it only adds new files). Make sure `api/__init__.py` exists there.
2. Run:

   ```bash
   cd frappe-bench
   bench --site <your-site> migrate
   bench build --app techpark
   bench --site <your-site> clear-cache
   bench restart            # or restart `bench start`
   ```
3. Open `http://<your-site>/app/customer-master`.

## Check these before migrating

- **Module name** — every JSON uses `"module": "TechPark"`. If your module is named
  differently (see `apps/techpark/techpark/modules.txt`), change it in all 4 JSON files and
  put the `doctype/` and `page/` folders inside that module's folder instead.
- **ERPNext** — if ERPNext is installed on this site it already has a `Customer` doctype,
  which would clash. In that case tell me and I'll rename ours (e.g. `TP Customer`).
- **Child tables used by Customer** — `Company contacts` (contacts grid) and
  `Organizaton Segment` (segments multi-select) must have *Is Child Table* ticked.
- **Link fields in your existing doctypes** — in Customer Product Production, Customer
  Turnover, Customer Segment Application, Wheel Consumption, Wheel Specification and
  Manufacturing Details, set the `customer` field's Options to `Customer` and the
  `plant` field (`address` in Customer Segment Application) to `Plant`.
  Those doctypes then show up as tabs on the customer screen automatically.
- **Roles** — the page is open to System Manager, Sales Manager and Sales User
  (Frappe CRM creates the last two). Edit `page/customer_master/customer_master.json`
  to change this.

## Adding more tabs later

Append an entry to `RELATED_TABS` in `api/customer_master.py` (doctype, link field,
columns). The page picks it up on reload — no JS changes needed.
