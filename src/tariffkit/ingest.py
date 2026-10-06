"""Turn an official schedule (HTML table or CSV) into dataset rows, and log changes.

Government pages change layout, so ingestion is deliberately semi-automatic:
`parse_html_tables` extracts every table that has a tariff-item column; you map
the columns once per source and review the result before committing it.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
from bs4 import BeautifulSoup

ITEM_RE = re.compile(r"^\d{4}(\.\d{2}){0,3}$")


def parse_html_tables(html: str) -> list[pl.DataFrame]:
    """Every <table> whose first column mostly looks like tariff items, as a DataFrame of strings."""
    soup = BeautifulSoup(html, "html.parser")
    frames = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            continue
        header, body = rows[0], [r for r in rows[1:] if len(r) == len(rows[0])]
        if not body:
            continue
        looks = sum(bool(ITEM_RE.match(r[0])) for r in body) / len(body)
        if looks >= 0.6:
            frames.append(pl.DataFrame(body, schema=[h or f"col{i}" for i, h in enumerate(header)], orient="row"))
    return frames


def to_dataset(table: pl.DataFrame, order_id: str, item_col: str, rate_col: str, desc_col: str | None,
               effective_from: str, source_url: str, cusma_exempt: bool) -> pl.DataFrame:
    def rate(text: str) -> float | None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text or "")
        return float(m.group(1)) / 100 if m else None

    return table.select(
        pl.lit(order_id).alias("order_id"),
        pl.col(item_col).alias("tariff_item"),
        (pl.col(desc_col) if desc_col else pl.lit("")).alias("description"),
        pl.col(rate_col).map_elements(rate, return_dtype=pl.Float64).alias("surtax_rate"),
        pl.lit(effective_from).alias("effective_from"),
        pl.lit(None, dtype=pl.Utf8).alias("effective_to"),
        pl.lit(str(cusma_exempt).lower()).alias("cusma_exempt"),
        pl.lit(source_url).alias("source_url"),
        pl.lit(date.today().isoformat()).alias("retrieved_at"),
    )


def diff(old: pl.DataFrame, new: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Added, removed and rate-changed items between two versions of surtax_items."""
    key = ["order_id", "tariff_item"]
    o = old.select(*key, pl.col("surtax_rate").cast(pl.Float64))
    n = new.select(*key, pl.col("surtax_rate").cast(pl.Float64))
    both = o.join(n, on=key, how="inner", suffix="_new")
    return {
        "added": n.join(o, on=key, how="anti"),
        "removed": o.join(n, on=key, how="anti"),
        "changed": both.filter(pl.col("surtax_rate") != pl.col("surtax_rate_new")),
    }


def snapshot(current: Path, history_dir: Path) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    target = history_dir / f"surtax_items_{date.today().isoformat()}.csv"
    target.write_bytes(current.read_bytes())
    return target
