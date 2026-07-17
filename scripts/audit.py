#!/usr/bin/env python3
"""Fail closed on identity/schema corruption and record observed coverage."""
from __future__ import annotations

import csv
import gzip
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rebuild_history import (build_history, last_seen_payload, latest_payload,
                             rows_from)

ROOT = Path(__file__).resolve().parent.parent
RAW, DERIVED, STATUS = ROOT / "raw", ROOT / "derived", ROOT / "status"
REQUIRED = ["ts", "model", "provider", "endpoint_tag", "endpoint_id",
            "identity_ambiguous", "state",
            "status", "up5m", "up30m", "up1d"]


def norm(value) -> str:
    return "" if value is None else str(value)


def main() -> None:
    raw_paths = sorted(RAW.glob("*/*.json.gz"))
    if not raw_paths:
        raise SystemExit("audit failed: no raw snapshots")
    stamps, snapshots = [], []
    for p in raw_paths:
        with gzip.open(p, "rt") as f:
            snap = json.load(f)
        snapshots.append(snap)
        stamps.append(datetime.fromisoformat(snap["generated"]))
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]

    latest = json.loads((STATUS / "latest.json").read_text())
    endpoints = latest.get("endpoints", [])
    keys = [(r["model"], r.get("endpoint_id")) for r in endpoints]
    if latest.get("schema_version") != 2 or any(k[1] is None for k in keys):
        raise SystemExit("audit failed: latest.json is not complete schema v2")
    if len(keys) != len(set(keys)):
        raise SystemExit("audit failed: duplicate endpoint identity in latest.json")

    csv_paths = sorted(DERIVED.glob("*.csv"))
    rows, actual_by_ts = 0, defaultdict(list)
    for p in csv_paths:
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != REQUIRED:
                raise SystemExit(f"audit failed: schema mismatch in {p}")
            for row in reader:
                actual_by_ts[row["ts"]].append(row)
                rows += 1

    expected_timestamps = {s["generated"] for s in snapshots}
    if set(actual_by_ts) != expected_timestamps:
        missing = sorted(expected_timestamps - set(actual_by_ts))[:3]
        extra = sorted(set(actual_by_ts) - expected_timestamps)[:3]
        raise SystemExit(f"audit failed: raw/derived timestamp mismatch "
                         f"missing={missing} extra={extra}")

    # Reparse every raw snapshot and compare every derived row. This checks more
    # than schema: it catches missing endpoints and parser drift.
    ambiguous_groups_seen = set()
    non_ambiguous_churn = defaultdict(set)
    for snap in snapshots:
        expected = rows_from(snap)
        actual = actual_by_ts[snap["generated"]]
        exp_map = {(r["model"], r["endpoint_id"]): r for r in expected}
        act_map = {(r["model"], r["endpoint_id"]): r for r in actual}
        if len(expected) != len(exp_map) or len(actual) != len(act_map):
            raise SystemExit(f"audit failed: duplicate endpoint in {snap['generated']}")
        if set(exp_map) != set(act_map):
            raise SystemExit(f"audit failed: endpoint set mismatch in {snap['generated']}")
        for key, exp in exp_map.items():
            act = act_map[key]
            for field in REQUIRED:
                if norm(exp[field]) != act[field]:
                    raise SystemExit(f"audit failed: {field} drift for {key} "
                                     f"at {snap['generated']}")
            group = (exp["model"], exp["endpoint_tag"])
            if exp["identity_ambiguous"]:
                ambiguous_groups_seen.add(group)
            else:
                non_ambiguous_churn[group].add(exp["endpoint_id"])
    churn = {k: ids for k, ids in non_ambiguous_churn.items() if len(ids) > 1}
    if churn:
        raise SystemExit(f"audit failed: stable tag identity churn: {list(churn)[:3]}")

    newest = snapshots[-1]
    expected_latest = rows_from(newest)
    expected_latest_keys = {(r["model"], r["endpoint_id"]) for r in expected_latest}
    if latest.get("generated") != newest["generated"] or set(keys) != expected_latest_keys:
        raise SystemExit("audit failed: latest.json does not match newest raw snapshot")
    if latest.get("models_polled") != len(newest["endpoints"]):
        raise SystemExit("audit failed: latest model count does not match raw query keys")

    v2 = [s for s in snapshots if s.get("schema_version") == 2]
    for snap in v2:
        if "data" not in snap.get("models", {}):
            continue  # catalog-fetch outage: run polled the fallback snapshot
        catalog_ids = {m["id"] for m in snap["models"]["data"]}
        if set(snap["endpoints"]) != catalog_ids:
            raise SystemExit(f"audit failed: v2 did not query exact catalog IDs at "
                             f"{snap['generated']}")

    # Re-derive all stateful artifacts from raw and compare complete content.
    incidents = [json.loads(x) for x in (STATUS / "incidents.jsonl").read_text().splitlines()
                 if x.strip()]
    _, expected_incidents, expected_last_seen, expected_latest, latest_n = \
        build_history(snapshots)
    if incidents != expected_incidents:
        raise SystemExit("audit failed: incidents.jsonl differs from raw-derived history")
    actual_last_seen = json.loads((STATUS / "last_seen.json").read_text())
    expected_last_seen_payload = last_seen_payload(
        expected_last_seen, snapshots[-1]["generated"])
    if actual_last_seen != expected_last_seen_payload:
        raise SystemExit("audit failed: last_seen.json differs from raw-derived history")
    expected_latest_payload = latest_payload(expected_latest, latest_n)
    if latest != expected_latest_payload:
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
        "legacy_base_model_snapshots": len(snapshots) - len(v2),
        "schema_v2_exact_model_snapshots": len(v2),
        "schema_v2_coverage_begins": v2[0]["generated"] if v2 else None,
        "coverage": {
            "observed_gaps": len(gaps),
            "median_minutes": round(statistics.median(gaps), 1) if gaps else None,
            "mean_minutes": round(statistics.mean(gaps), 1) if gaps else None,
            "max_minutes": round(max(gaps), 1) if gaps else None,
            "gaps_over_120_minutes": sum(x > 120 for x in gaps),
            "warning": "scheduled hourly; actual coverage is best-effort",
        },
    }
    (STATUS / "audit.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
