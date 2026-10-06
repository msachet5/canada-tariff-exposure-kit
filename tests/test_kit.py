from datetime import date
from pathlib import Path

import polars as pl

from tariffkit.exposure import exposure, summary
from tariffkit.ingest import diff, parse_html_tables, to_dataset
from tariffkit.rates import load_rates, normalise_item, rate_for

ROOT = Path(__file__).resolve().parents[1]
RATES = ROOT / "data" / "EXAMPLE_surtax_items.csv"


def test_normalise():
    assert normalise_item("9999.10.00") == "99991000"
    assert normalise_item(None) == ""


def test_rate_lookup_prefix_and_dates():
    r = load_rates(RATES)
    assert rate_for(r, "9999.10.00", date(2026, 3, 1))["surtax_rate"] == 0.25
    assert rate_for(r, "9999.10.00", date(2026, 7, 1))["surtax_rate"] == 0.50  # later order wins
    assert rate_for(r, "9999.20.40", date(2026, 3, 1))["order_id"] == "EXAMPLE-1"  # heading-level match
    assert rate_for(r, "9999.10.00", date(2025, 12, 31)) is None


def test_exposure_cases():
    p = pl.read_csv(ROOT / "examples" / "purchases_example.csv", try_parse_dates=True, schema_overrides={"tariff_item": pl.Utf8})
    lines = exposure(p, load_rates(RATES))
    got = dict(zip(lines["description"] + "|" + lines["date"].cast(pl.Utf8), lines["surtax_cad"], strict=True))
    assert got["fictional widget|2026-02-10"] == 2500
    assert got["fictional widget|2026-07-15"] == 4000
    assert got["fictional gadget|2026-03-01"] == 0  # CUSMA claimed on an exempt entry
    assert got["fictional gadget|2026-03-05"] == 600
    assert got["fictional part|2026-04-01"] == 0  # not US origin
    assert got["unlisted item|2026-04-02"] == 0
    s = summary(lines)
    assert s["cusma_checks"].height == 1
    assert s["by_supplier"]["supplier"][0] == "Example Supplier A"


def test_what_if():
    p = pl.read_csv(ROOT / "examples" / "purchases_example.csv", try_parse_dates=True, schema_overrides={"tariff_item": pl.Utf8})
    lines = exposure(p, load_rates(RATES), what_if_rate=0.10)
    assert lines["surtax_cad"].max() == 1000


def test_html_ingest_and_diff():
    tables = parse_html_tables((ROOT / "tests/fixtures/schedule.html").read_text())
    assert len(tables) == 1
    ds = to_dataset(tables[0], "TEST", "Tariff item", "Surtax", "Description", "2026-01-01", "https://example.org", False)
    assert ds["surtax_rate"].to_list() == [0.25, 0.15, 0.50]
    old = ds.head(2).with_columns(pl.col("surtax_rate").cast(pl.Utf8))
    new = ds.with_columns(pl.when(pl.col("tariff_item") == "9999.20").then(0.2).otherwise(pl.col("surtax_rate")).alias("surtax_rate"))
    d = diff(old, new)
    assert d["added"].height == 1 and d["changed"].height == 1 and d["removed"].height == 0


def test_empty_dataset_is_clear(tmp_path):
    from tariffkit.cli import main

    assert main(["--rates", str(ROOT / "data" / "surtax_items.csv"), "exposure", str(ROOT / "examples/purchases_example.csv"), "--out", str(tmp_path)]) == 2
