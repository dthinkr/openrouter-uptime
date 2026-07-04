#!/usr/bin/env python3
"""Consolidate the git registry into tidy dataset artifacts for HF / Kaggle.

Reads the per-run CSVs, the incident log, and the model/provider catalogs;
writes Parquet plus the dataset card into a gitignored `build/` dir. Run daily:
this is the clean, discoverable mirror of the high-frequency git history.

    python3 scripts/export.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DERIVED, STATUS, CARD, OUT = (ROOT / "derived", ROOT / "status",
                              ROOT / "card", ROOT / "build")


def main() -> None:
    OUT.mkdir(exist_ok=True)

    frames = [pd.read_csv(f) for f in sorted(DERIVED.glob("*.csv"))]
    readings = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not readings.empty:
        readings["ts"] = pd.to_datetime(readings["ts"], utc=True)
        readings.to_parquet(OUT / "readings.parquet", index=False)
        readings.tail(200_000).to_csv(OUT / "readings_sample.csv", index=False)

    inc_path = STATUS / "incidents.jsonl"
    inc = [json.loads(x) for x in inc_path.read_text().splitlines() if x.strip()] \
        if inc_path.exists() else []
    if inc:
        pd.DataFrame(inc).to_parquet(OUT / "incidents.parquet", index=False)

    for name in ("models", "providers"):
        p = STATUS / f"{name}.json"
        if p.exists():
            pd.json_normalize(json.loads(p.read_text())[name]).to_parquet(
                OUT / f"{name}.parquet", index=False)

    if (CARD / "README.md").exists():
        shutil.copy(CARD / "README.md", OUT / "README.md")

    span = (f"{readings['ts'].min():%Y-%m-%d} to {readings['ts'].max():%Y-%m-%d}"
            if not readings.empty else "")
    (OUT / "stats.json").write_text(json.dumps({
        "readings": int(len(readings)), "incidents": len(inc),
        "days": len({f.stem for f in DERIVED.glob("*.csv")}), "span": span},
        indent=1))
    print(f"exported: {len(readings)} readings, {len(inc)} incidents ({span})")


if __name__ == "__main__":
    main()
