#!/usr/bin/env python3
"""Fail closed on identity/schema corruption and record observed coverage.

Streams: one raw snapshot and one day of derived rows in memory at a time.
The previous version loaded every snapshot and every derived row up front,
which grew past the GitHub runner's memory at ~2,500 snapshots and was
OOM-killed four days running -- taking the staleness alarm that shared its
job down with it.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rebuild_history import (History, iter_snapshots, last_seen_payload,
                             latest_payload)

ROOT = Path(__file__).resolve().parent.parent
RAW, DERIVED, STATUS = ROOT / "raw", ROOT / "derived", ROOT / "status"
REQUIRED = ["ts", "model", "provider", "endpoint_tag", "endpoint_id",
            "identity_ambiguous", "state",
            "status", "up5m", "up30m", "up1d"]


def norm(value) -> str:
    return "" if value is None else str(value)


def load_day(path: Path) -> dict[str, list[dict]]:
    by_ts: dict[str, list[dict]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REQUIRED:
            raise SystemExit(f"audit failed: schema mismatch in {path}")
        for row in reader:
            by_ts[row["ts"]].append(row)
    return by_ts


def main() -> None:
    raw_paths = sorted(RAW.glob("*/*.json.gz"))
    if not raw_paths:
        raise SystemExit("audit failed: no raw snapshots")

    latest = json.loads((STATUS / "latest.json").read_text())
    endpoints = latest.get("endpoints", [])
    keys = [(r["model"], r.get("endpoint_id")) for r in endpoints]
    if latest.get("schema_version") != 2 or any(k[1] is None for k in keys):
        raise SystemExit("audit failed: latest.json is not complete schema v2")
    if len(keys) != len(set(keys)):
        raise SystemExit("audit failed: duplicate endpoint identity in latest.json")

    csv_days = {p.stem: p for p in DERIVED.glob("*.csv")}
    unvisited_days = set(csv_days)
    history = History()
    stamps: list[datetime] = []
    rows, v2, legacy, first_v2 = 0, 0, 0, None
    ambiguous_groups_seen = set()
    non_ambiguous_churn = defaultdict(set)
    day, day_rows = None, {}

    def close_day() -> None:
        if day_rows:
            extra = sorted(day_rows)[:3]
            raise SystemExit(f"audit failed: raw/derived timestamp mismatch "
                             f"missing=[] extra={extra}")

    # Reparse every raw snapshot and compare every derived row. This checks
    # more than schema: it catches missing endpoints and parser drift.
    for snap in iter_snapshots(raw_paths):
        generated = snap["generated"]
        stamps.append(datetime.fromisoformat(generated))
        this_day = generated[:10]
        if this_day != day:
            close_day()
            if this_day not in unvisited_days:
                raise SystemExit(f"audit failed: raw/derived timestamp mismatch "
                                 f"missing=[{generated!r}] extra=[]")
            unvisited_days.discard(this_day)
            day, day_rows = this_day, load_day(csv_days[this_day])
        expected = history.feed(snap)
        actual = day_rows.pop(generated, None)
        if actual is None:
            raise SystemExit(f"audit failed: raw/derived timestamp mismatch "
                             f"missing=[{generated!r}] extra=[]")
        rows += len(actual)
        exp_map = {(r["model"], r["endpoint_id"]): r for r in expected}
        act_map = {(r["model"], r["endpoint_id"]): r for r in actual}
        if len(expected) != len(exp_map) or len(actual) != len(act_map):
            raise SystemExit(f"audit failed: duplicate endpoint in {generated}")
        if set(exp_map) != set(act_map):
            raise SystemExit(f"audit failed: endpoint set mismatch in {generated}")
        for key, exp in exp_map.items():
            act = act_map[key]
            for field in REQUIRED:
                if norm(exp[field]) != act[field]:
                    raise SystemExit(f"audit failed: {field} drift for {key} "
                                     f"at {generated}")
            group = (exp["model"], exp["endpoint_tag"])
            if exp["identity_ambiguous"]:
                ambiguous_groups_seen.add(group)
            else:
                non_ambiguous_churn[group].add(exp["endpoint_id"])
        if snap.get("schema_version") == 2:
            v2 += 1
            first_v2 = first_v2 or generated
            if "data" in snap.get("models", {}):
                catalog_ids = {m["id"] for m in snap["models"]["data"]}
                if set(snap["endpoints"]) != catalog_ids:
                    raise SystemExit(f"audit failed: v2 did not query exact catalog "
                                     f"IDs at {generated}")
        else:
            legacy += 1  # catalog-fetch outage runs polled the fallback snapshot
    close_day()
    if unvisited_days:
        raise SystemExit(f"audit failed: derived days with no raw snapshot: "
                         f"{sorted(unvisited_days)[:3]}")

    churn = {k: ids for k, ids in non_ambiguous_churn.items() if len(ids) > 1}
    if churn:
        raise SystemExit(f"audit failed: stable tag identity churn: {list(churn)[:3]}")

    newest, expected_latest_rows = history.latest
    expected_latest_keys = {(r["model"], r["endpoint_id"]) for r in expected_latest_rows}
    if latest.get("generated") != newest["generated"] or set(keys) != expected_latest_keys:
        raise SystemExit("audit failed: latest.json does not match newest raw snapshot")
    if latest.get("models_polled") != len(newest["endpoints"]):
        raise SystemExit("audit failed: latest model count does not match raw query keys")

    # Compare the stateful artifacts against the raw-derived history.
    incidents = [json.loads(x) for x in (STATUS / "incidents.jsonl").read_text().splitlines()
                 if x.strip()]
    if incidents != history.incidents:
        raise SystemExit("audit failed: incidents.jsonl differs from raw-derived history")
    actual_last_seen = json.loads((STATUS / "last_seen.json").read_text())
    if actual_last_seen != last_seen_payload(history.last_seen, newest["generated"]):
        raise SystemExit("audit failed: last_seen.json differs from raw-derived history")
    if latest != latest_payload(history.latest, history.latest_transition_count):
        raise SystemExit("audit failed: latest.json differs from raw-derived history")

    inc_keys = [(x["ts"], x["model"], x.get("endpoint_id"), x["event"])
                for x in incidents]
    if len(inc_keys) != len(set(inc_keys)):
        raise SystemExit("audit failed: duplicate incident transition")
    by_endpoint = defaultdict(list)
    for incident in incidents:
        by_endpoint[(incident["model"], incident.get("endpoint_id"))].append(
            incident["event"])
    repeated_edges = sum(a == b for events in by_endpoint.values()
                         for a, b in zip(events, events[1:]))
    if repeated_edges:
        raise SystemExit(f"audit failed: {repeated_edges} non-alternating incident edges")

    gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]
    report = {
        "schema_version": 2,
        "passed": True,
        "raw_snapshots": len(raw_paths),
        "derived_rows": rows,
        "latest_endpoint_rows": len(endpoints),
        "unique_latest_endpoint_ids": len(set(keys)),
        "incident_transitions": len(incidents),
        "exact_duplicate_incidents": 0,
        "non_alternating_incident_edges": 0,
        "gap_bridged_transitions": sum(bool(x.get("observation_gap")) for x in incidents),
        "ambiguous_model_tag_groups": len(ambiguous_groups_seen),
        "non_ambiguous_identity_churn_groups": 0,
        "raw_to_derived_rows_verified": rows,
        "stateful_artifacts_exact_match": True,
        "legacy_base_model_snapshots": legacy,
        "schema_v2_exact_model_snapshots": v2,
        "schema_v2_coverage_begins": first_v2,
        "coverage": {
            "observed_gaps": len(gaps),
            "median_minutes": round(statistics.median(gaps), 1) if gaps else None,
            "mean_minutes": round(statistics.mean(gaps), 1) if gaps else None,
            "max_minutes": round(max(gaps), 1) if gaps else None,
            "gaps_over_120_minutes": sum(x > 120 for x in gaps),
            "note": "sampling characteristics are published in status/coverage.json",
        },
    }
    (STATUS / "audit.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
