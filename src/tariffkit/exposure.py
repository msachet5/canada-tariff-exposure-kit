"""Surtax exposure from purchase history.

Purchases need: tariff_item (or hs_code), origin (ISO country, e.g. US), customs_value_cad, date.
Optional: supplier, description, cusma_claimed (true/false), quantity.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from .rates import normalise_item, rate_for

US = {"US", "USA", "UNITED STATES"}


def exposure(purchases: pl.DataFrame, rates: pl.DataFrame, remission: pl.DataFrame | None = None,
             what_if_rate: float | None = None) -> pl.DataFrame:
    """One row per purchase line with the surtax that would apply, and why."""
    p = purchases.rename({"hs_code": "tariff_item"}) if "hs_code" in purchases.columns and "tariff_item" not in purchases.columns else purchases
    for col in ("tariff_item", "origin", "customs_value_cad", "date"):
        if col not in p.columns:
            raise KeyError(f"purchases need a '{col}' column")
    if p.schema["date"] == pl.Utf8:
        p = p.with_columns(pl.col("date").str.to_date())
    if "cusma_claimed" not in p.columns:
        p = p.with_columns(pl.lit(False).alias("cusma_claimed"))
    rows: list[dict[str, Any]] = []
    for r in p.iter_rows(named=True):
        out = dict(r)
        origin = str(r["origin"] or "").strip().upper()
        hit = rate_for(rates, r["tariff_item"], r["date"]) if origin in US else None
        rate, reason = 0.0, "origin not US" if origin not in US else "item not listed"
        if hit:
            claimed = str(r["cusma_claimed"]).lower() in ("true", "1", "yes")
            if hit["cusma_exempt"] and claimed:
                rate, reason = 0.0, f"listed in {hit['order_id']} but CUSMA-exempt and CUSMA claimed"
            else:
                rate = what_if_rate if what_if_rate is not None else hit["surtax_rate"]
                reason = f"{hit['order_id']} at {rate:.0%}"
                if hit["cusma_exempt"] and not claimed:
                    reason += "; CUSMA-exempt if the goods qualify: check origin documents"
            out["order_id"] = hit["order_id"]
        else:
            out["order_id"] = None
        out["surtax_rate"] = rate
        out["surtax_cad"] = round(float(r["customs_value_cad"]) * rate, 2)
        out["reason"] = reason
        out["remission_lead"] = _remission(remission, r["tariff_item"], r["date"]) if remission is not None and rate > 0 else None
        rows.append(out)
    return pl.DataFrame(rows)


def _remission(remission: pl.DataFrame, item: str, on: date) -> str | None:
    digits = normalise_item(item)
    for r in remission.iter_rows(named=True):
        pref = normalise_item(r["tariff_item_prefix"])
        start = r.get("applies_from")
        if pref and digits.startswith(pref) and (start is None or str(start) <= str(on)):
            return f"{r['remission_id']}: {r['description']}"
    return None


def summary(lines: pl.DataFrame) -> dict[str, pl.DataFrame]:
    hit = lines.filter(pl.col("surtax_cad") > 0)
    return {
        "by_supplier": (hit.group_by("supplier").agg(pl.col("surtax_cad").sum(), pl.col("customs_value_cad").sum(), pl.len().alias("lines"))
                        .sort("surtax_cad", descending=True)) if "supplier" in hit.columns else pl.DataFrame(),
        "by_item": hit.group_by("tariff_item", "order_id").agg(pl.col("surtax_cad").sum(), pl.col("customs_value_cad").sum())
        .sort("surtax_cad", descending=True),
        "by_month": hit.with_columns(pl.col("date").dt.truncate("1mo").alias("month")).group_by("month")
        .agg(pl.col("surtax_cad").sum()).sort("month"),
        "cusma_checks": lines.filter(pl.col("reason").str.contains("check origin documents")),
    }
