# Warehouse management (WMS)

HSM are a freight forwarder. Their warehouses in Qatar, Dubai and China are buffers
between two legs of a shipment, not fulfilment centres, and **nothing stored in them
belongs to HSM**. That single fact decides the whole design:

- **No Item, no Stock Ledger Entry, no Bin.** Cargo is identified by package type, count
  and a free-text description. This is why the Warehouse 3PL app was the wrong engine —
  its `Receiving Line` requires `item_code`.
- **The unit of record is the waybill.** One Receipt Note, one waybill, one customer.
- **The unit of measure is CBM**, computed as `l × w × h ÷ 1e6 × qty` per package row.

Requirement source: meeting 2026-09-05 + the client's own `WAREHOUSE FLOW CHART.pdf`.

## The flow

```
Receipt Note ──┐
Receipt Note ──┼──▶ ONE Job Details (job_type = CONSOLE) ──▶ arrival ──▶ delivery ──▶ POD
Receipt Note ──┘        └── one Waybill Console per receipt, one per customer
```

A console job holds **many customers** — that is the point of it. HSM collect from ten to
twenty customers, load one container, and move it as a single shipment, so the cost is a
single cost and the job header carries the *company*, not a customer.

`Job Details.job_id` is a Link to **Customer** despite its name, so a console job leaves
it blank. Its only consumers display it (four sales-person reports and the JD/POD print
formats) and none of them break on a null.

## Modules

| File | What it owns |
|---|---|
| `capacity.py` | The **only** writer of a Warehouse Unit's free space. Row-locked, guarded both ways. |
| `rates.py` | Storage rate lookup by (customer, cargo type). `find_` returns None, `get_` throws. |
| `consolidation.py` | Receipt Notes → one CONSOLE job + one Waybill Console each. |
| `movement.py` | Arrival at the destination, delivery per waybill, POD creation. |
| `storage_billing.py` | Daily accrual into Storage Charge, then monthly Sales Invoices. |
| `testing.py` | Idempotent fixtures for the test suite. Not a test module. |

## Capacity moves on four events, and only through `capacity.move_capacity()`

| Event | Origin | Destination |
|---|---|---|
| Receipt submitted | −CBM | — |
| Movement job created | +CBM | — |
| Arrival confirmed | — | −CBM |
| Delivery recorded | — | +CBM |

Four callers is exactly the shape that produced lost updates before, so they all funnel
through one locked function that also maintains `occupied_capacity_cbm` and
`utilisation_pct`. A release that would push a warehouse above its total capacity is
**refused** — that means an event fired twice.

`Warehouse Unit.total_area_capacity` / `total_available_capacity` keep their old
fieldnames and hold CBM. Renaming them would have meant a data migration plus an
unverifiable sweep of site-only Client Scripts; the labels say CBM instead. Read them
through `capacity.get_capacity()`.

## Storage billing

Rate is **per CBM per day**, keyed on customer *and* cargo class, agreed by quotation and
then fixed until renegotiated. Days are counted **inclusive of both ends**.

```
19.00 CBM × 12 days × QAR 3.00/CBM/day  =  QAR   684.00   (General)
19.00 CBM × 12 days × QAR 6.00/CBM/day  =  QAR 1,368.00   (Dangerous Cargo)
```

A missing or zero rate **throws** at invoicing and is **reported** at accrual. In
`warehouse_3pl`, `create_billing_transaction()` returned early when rate and minimum were
both zero, so a missing rate wrote no billing row at all and the work stayed billable
forever while looking finished. Not repeating that is the reason this module exists.

Accrual may run on the scheduler (`0 2 1 * *`) because it is arithmetic. **Invoicing is
always a human action** — HSM read the figures before billing.

`WMS-STORAGE` is a non-stock service item for the invoice line. It is HSM's own service,
not customer cargo, so it does not contradict the no-Item rule; without an `item_code`
ERPNext refuses the invoice with "Income Account None does not belong to Company X".

## Open with the client

- Is the storage rate **QAR 40/CBM/month** (their historical data) or **QAR 2–6/CBM/day**
  (stated on the call)? The engine is rate-agnostic; the numbers are not seeded.
- Are the existing warehouse capacity figures **m² or CBM**? Until restated, the
  over-capacity block cannot be trusted.
- Is "Receiver Details" a party distinct from the end customer? (Flow chart items 4 and 5.)

## Not built, deliberately

- **A warehouse role.** Every DocType here is System Manager only, matching the rest of
  the app. 11 of 17 users already hold System Manager because no logistics role exists —
  worth fixing, but it is a permission change on a live site and nobody asked for it.
- **Handling charges.** HSM invoice handling as lump sums; only storage is automated.
