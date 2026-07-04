#!/usr/bin/env python3
"""Consolidate the git registry into tidy dataset artifacts for HF / Kaggle.

Reads the per-run CSVs, the incidents log, and the model catalog; writes
partition-friendly Parquet (+ a CSV fallback) plus a dataset card into
`dataset/`. Run daily, this is the clean, discoverable mirror of the
high-frequency git history.

    python3 scripts/export.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, STATUS, OUT = ROOT / "data", ROOT / "status", ROOT / "dataset"


def main() -> None:
    OUT.mkdir(exist_ok=True)

    # 1. readings, every endpoint reading across all days
    frames = [pd.read_csv(f) for f in sorted(DATA.glob("*.csv"))]
    readings = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not readings.empty:
        readings["ts"] = pd.to_datetime(readings["ts"], utc=True)
        readings.to_parquet(OUT / "readings.parquet", index=False)
        readings.tail(200_000).to_csv(OUT / "readings_sample.csv", index=False)

    # 2. incidents, outage start/recovery log
    inc_path = STATUS / "incidents.jsonl"
    inc = [json.loads(l) for l in inc_path.read_text().splitlines() if l.strip()] \
        if inc_path.exists() else []
    if inc:
        pd.DataFrame(inc).to_parquet(OUT / "incidents.parquet", index=False)

    # 3. model catalog snapshot
    cat_path = STATUS / "models.json"
    if cat_path.exists():
        cat = json.loads(cat_path.read_text())
        pd.DataFrame(cat["models"]).to_parquet(OUT / "models.parquet",
                                               index=False)

    # 4. coverage stats for the card
    n_days = len({f.stem for f in DATA.glob("*.csv")})
    span = ""
    if not readings.empty:
        span = f"{readings['ts'].min():%Y-%m-%d} → {readings['ts'].max():%Y-%m-%d}"
    (OUT / "stats.json").write_text(json.dumps({
        "readings": int(len(readings)),
        "incidents": len(inc),
        "days": n_days,
        "span": span,
        "models": len(json.loads(cat_path.read_text())["models"])
        if cat_path.exists() else 0,
    }, indent=1))
    print(f"exported: {len(readings)} readings, {len(inc)} incidents, "
          f"{n_days} days ({span})")


if __name__ == "__main__":
    main()
