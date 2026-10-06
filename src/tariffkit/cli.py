"""tariffkit command line.

    tariffkit exposure purchases.csv [--rates data/surtax_items.csv] [--remission data/remission.csv] [--out exposure]
    tariffkit lookup 8501.10.00 --date 2026-09-30
    tariffkit tables page.html                       # list tariff tables found in a saved official page
    tariffkit diff old.csv new.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import polars as pl

from .exposure import exposure, summary
from .ingest import diff, parse_html_tables
from .rates import load_rates, rate_for

DISCLAIMER = "Information only, not customs or legal advice. Confirm with a licensed customs broker or the CBSA."


def cmd_exposure(a: argparse.Namespace) -> int:
    rates = load_rates(a.rates)
    if rates.is_empty():
        print("The rates file is empty. Populate data/surtax_items.csv from the official schedules first "
              "(or use data/EXAMPLE_surtax_items.csv for a demo).", file=sys.stderr)
        return 2
    purchases = pl.read_csv(a.purchases, try_parse_dates=True, infer_schema_length=10000, schema_overrides={"tariff_item": pl.Utf8, "hs_code": pl.Utf8})
    remission = pl.read_csv(a.remission, infer_schema=False) if a.remission and Path(a.remission).exists() else None
    lines = exposure(purchases, rates, remission, what_if_rate=a.what_if_rate)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lines.write_csv(out / "lines.csv")
    s = summary(lines)
    for name, t in s.items():
        if t.height:
            t.write_csv(out / f"{name}.csv")
    total = lines["surtax_cad"].sum()
    us_value = lines.filter(pl.col("origin").str.to_uppercase().is_in(["US", "USA"]))["customs_value_cad"].sum()
    print(f"{lines.height} purchase lines; surtax exposure CAD {total:,.2f} on CAD {us_value:,.2f} of US-origin purchases")
    if s["by_supplier"].height:
        print(s["by_supplier"].head(10))
    print(f"{s['cusma_checks'].height} lines are CUSMA-exempt if the goods qualify: check origin documents.")
    print(DISCLAIMER)
    return 0


def cmd_lookup(a: argparse.Namespace) -> int:
    hit = rate_for(load_rates(a.rates), a.item, date.fromisoformat(a.date) if a.date else date.today())
    print(hit or "not listed on that date")
    print(DISCLAIMER)
    return 0


def cmd_tables(a: argparse.Namespace) -> int:
    for i, t in enumerate(parse_html_tables(Path(a.html).read_text(encoding="utf-8"))):
        print(f"table {i}: {t.height} rows, columns {t.columns}")
        print(t.head(5))
    return 0


def cmd_diff(a: argparse.Namespace) -> int:
    d = diff(pl.read_csv(a.old, infer_schema=False), pl.read_csv(a.new, infer_schema=False))
    for k, v in d.items():
        print(f"{k}: {v.height}")
        if v.height:
            print(v.head(20))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tariffkit", epilog=DISCLAIMER)
    p.add_argument("--rates", default="data/surtax_items.csv")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("exposure")
    s.add_argument("purchases")
    s.add_argument("--remission", default="data/remission.csv")
    s.add_argument("--what-if-rate", type=float, help="apply one rate to every listed item, e.g. 0.25")
    s.add_argument("--out", default="exposure")
    s.set_defaults(func=cmd_exposure)
    s = sub.add_parser("lookup")
    s.add_argument("item")
    s.add_argument("--date")
    s.set_defaults(func=cmd_lookup)
    s = sub.add_parser("tables")
    s.add_argument("html")
    s.set_defaults(func=cmd_tables)
    s = sub.add_parser("diff")
    s.add_argument("old")
    s.add_argument("new")
    s.set_defaults(func=cmd_diff)
    a = p.parse_args(argv)
    return int(a.func(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
