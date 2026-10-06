# Data

**Nothing in `surtax_items.csv` is populated yet.** It must be filled from the official sources (the Department of Finance Canada surtax orders and their schedules, and CBSA customs notices) with `tariffkit ingest`, then checked line by line before first publication. `EXAMPLE_surtax_items.csv` contains fictional tariff items (heading 9999) used only by tests and the demo.

| File | One row per | Key |
|---|---|---|
| `orders.csv` | surtax order (each order or amendment) | order_id |
| `surtax_items.csv` | tariff item in an order, with rate and dates | order_id + tariff_item |
| `remission.csv` | remission framework or order that may refund surtax | remission_id |
| `history/` | a dated snapshot of `surtax_items.csv` per change, plus the diff | date |

Rules:

* `tariff_item` keeps Canada's dotted format (`1234.56.78`). Entries at 6 or 4 digits apply to every item beneath them.
* `surtax_rate` is a fraction (0.25 = 25%).
* `effective_to` empty means still in force.
* `cusma_exempt` records whether the order exempts goods that qualify for CUSMA preferential treatment, as the order states it.
* Every row has the `source_url` it was taken from and the date it was retrieved.

This dataset is information, not customs or legal advice. Confirm treatment of any shipment with a licensed customs broker or the CBSA.
