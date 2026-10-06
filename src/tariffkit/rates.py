"""Load the surtax dataset and look up the rate for a tariff item on a date."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

SCHEMA = {
    "order_id": pl.Utf8, "tariff_item": pl.Utf8, "description": pl.Utf8, "surtax_rate": pl.Float64,
    "effective_from": pl.Utf8, "effective_to": pl.Utf8, "cusma_exempt": pl.Utf8, "source_url": pl.Utf8, "retrieved_at": pl.Utf8,
}


def normalise_item(code: str | int | None) -> str:
    """Digits only: '8501.10.00' -> '85011000'. Accepts HS codes with or without dots."""
    if code is None:
        return ""
    return "".join(ch for ch in str(code) if ch.isdigit())


def load_rates(path: str | Path) -> pl.DataFrame:
    df = pl.read_csv(path, schema_overrides=SCHEMA)
    return df.with_columns(
        pl.col("tariff_item").map_elements(normalise_item, return_dtype=pl.Utf8).alias("item_digits"),
        pl.col("effective_from").str.to_date(strict=False),
        pl.col("effective_to").str.to_date(strict=False),
        pl.col("cusma_exempt").str.to_lowercase().is_in(["true", "1", "yes"]).alias("cusma_exempt"),
    )


def rate_for(rates: pl.DataFrame, item: str, on: date) -> dict | None:
    """Most specific matching entry in force on the date (longest prefix wins, then latest effective_from)."""
    digits = normalise_item(item)
    live = rates.filter(
        (pl.col("effective_from") <= on) & (pl.col("effective_to").is_null() | (pl.col("effective_to") >= on))
    )
    hits = [r for r in live.iter_rows(named=True) if digits.startswith(r["item_digits"]) and r["item_digits"]]
    if not hits:
        return None
    hits.sort(key=lambda r: (len(r["item_digits"]), r["effective_from"]), reverse=True)
    return hits[0]
