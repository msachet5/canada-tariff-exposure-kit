# Canada Tariff Exposure Kit

**Canada surtax exposure calculator and a versioned dataset of Canada's surtax orders on US goods.** Upload your purchase history (tariff item, origin, customs value) and get the surtax you are exposed to, by supplier, item and month, with CUSMA flags and remission leads.

Law firms and customs brokers publish explainers of each surtax order. Nobody publishes the change history as data, joined to a calculator a buyer can run on their own purchases. This kit does both.

> **Status: the dataset is not populated yet.** `data/surtax_items.csv` must be filled from the official schedules (Department of Finance Canada surtax orders, CBSA customs notices) and reviewed line by line before first release. The demo uses `data/EXAMPLE_surtax_items.csv`, which contains fictional tariff items only.

## Use it

```bash
pip install -e .
tariffkit --rates data/EXAMPLE_surtax_items.csv exposure examples/purchases_example.csv
tariffkit --rates data/surtax_items.csv exposure my_purchases.csv --out exposure/
tariffkit lookup 8501.10.00 --date 2026-09-30
tariffkit exposure my_purchases.csv --what-if-rate 0.25        # scenario: one rate on every listed item
```

Purchases need `date`, `tariff_item` (or `hs_code`), `origin` and `customs_value_cad`; `supplier` and `cusma_claimed` are optional. Output: `lines.csv` (every line with the rate, the order that applies and why), plus totals by supplier, item and month, and the lines where a CUSMA claim would change the answer.

## Maintaining the dataset

1. Save the official schedule page, then `tariffkit tables page.html` to see the tariff tables it contains.
2. Map columns with `tariffkit.ingest.to_dataset` (order id, item column, rate column, effective date, source URL, whether the order exempts CUSMA-qualifying goods).
3. `tariffkit diff data/surtax_items.csv new.csv` to review added, removed and changed items.
4. Commit with a snapshot in `data/history/` and a line in `CHANGELOG.md`. Every change is a release, so the history is citable.

## Rules the calculator applies

* Only US-origin lines can be surtaxed.
* The most specific tariff entry in force on the purchase date wins (10-digit over 8 over 6), then the latest order.
* If the order exempts CUSMA-qualifying goods and the line claims CUSMA, the rate is zero; if it does not claim CUSMA, the line is flagged for an origin-document check.
* Remission frameworks listed in `data/remission.csv` are shown as leads; whether a refund applies depends on conditions the kit does not check.

## Not advice

This is information, not customs or legal advice. Confirm the treatment of any shipment with a licensed customs broker or the CBSA.

Built by [Sachet Mulimani](https://www.linkedin.com/in/sachet-s-mulimani). [CleverChainAI](https://cleverchainai.com) runs this analysis for distributors as a service. MIT licensed.
