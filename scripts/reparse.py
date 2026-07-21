#!/usr/bin/env python3
"""Rebuild the derived rows for one run from its raw archive.

Proves the raw/ archive is self-sufficient: if poll.py's parsing were ever
wrong, the full dataset re-derives from raw/ alone. Prints the CSV rows that
poll.py would have written for that snapshot.

Usage:
    python3 scripts/reparse.py raw/2026-07-04/140117.json.gz
"""
from __future__ import annotations

import csv
import gzip
import json
import sys


def state_of(status, up30m) -> str:
    # OpenRouter status code: 0 healthy, -2 degraded, -5 down.
    if status == -5 or (up30m is not None and up30m < 50.0):
        return "down"
    if status == -2 or (up30m is not None and up30m < 98.0):
        return "degraded"
    if up30m is None:
        return "idle"
    return "up"


def main(path: str) -> None:
    with gzip.open(path, "rt") as f:
        snap = json.load(f)
    iso = snap["generated"]
    w = csv.writer(sys.stdout)
    w.writerow(["ts", "model", "provider", "state",
                "status", "up5m", "up30m", "up1d"])
    for slug, raw in sorted(snap["endpoints"].items()):
        eps = raw.get("data", {}).get("endpoints", []) if isinstance(raw, dict) \
            else []
        if not eps:
            w.writerow([iso, slug, None, "idle", None, None, None, None])
            continue
        for ep in eps:
            st = ep.get("status")
            u30 = ep.get("uptime_last_30m")
            w.writerow([iso, slug, ep.get("provider_name"),
                        state_of(st, u30), st, ep.get("uptime_last_5m"),
                        u30, ep.get("uptime_last_1d")])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
