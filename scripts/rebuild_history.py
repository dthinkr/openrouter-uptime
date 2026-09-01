#!/usr/bin/env python3
"""Rebuild all derived readings, incidents, and latest.json from raw archives.

This is the canonical repair path after a parser or identity-schema change.
It never edits raw archives. Endpoint identity is `(model, endpoint_id)`.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, DERIVED, STATUS = ROOT / "raw", ROOT / "derived", ROOT / "status"
FIELDS = ["ts", "model", "provider", "endpoint_tag", "endpoint_id",
          "identity_ambiguous", "state", "status",
          "up5m", "up30m", "up1d"]
STABLE = {"up", "degraded", "down"}


def state_of(status, up30m) -> str:
    if status == -5 or (up30m is not None and up30m < 50.0):
        return "down"
    if status == -2 or (up30m is not None and up30m < 98.0):
        return "degraded"
    if up30m is None:
        return "idle"
    return "up"


def endpoint_base(ep) -> str:
    return str(ep.get("tag") or ep.get("name") or ep.get("provider_name")
               or "unknown")


def endpoint_identities(eps) -> list[tuple[str, bool]]:
    from collections import Counter
    bases = [endpoint_base(ep) for ep in eps]
    counts = Counter(bases)
    out = []
    for base, ep in zip(bases, eps):
        if counts[base] == 1:
            out.append((base, False)); continue
        signature = {k: ep.get(k) for k in (
            "name", "model_id", "provider_name", "pricing",
            "quantization", "context_length", "max_completion_tokens",
            "max_prompt_tokens", "supports_implicit_caching")}
        signature["tag"] = base
        signature["supported_parameters"] = sorted(ep.get("supported_parameters") or [])
        raw = json.dumps(signature, sort_keys=True, separators=(",", ":"))
        out.append((f"{base}#{hashlib.sha256(raw.encode()).hexdigest()[:10]}", True))
    # Endpoints that agree on every descriptive field get an ordinal in array
    # order; see make_endpoint_identities in poll.py. Kept byte-for-byte in
    # step with it: the audit replays raw/ through this copy.
    counts = Counter(i for i, _ in out)
    seen: dict[str, int] = {}
    final = []
    for ident, ambiguous in out:
        if counts[ident] == 1:
            final.append((ident, ambiguous)); continue
        seen[ident] = seen.get(ident, 0) + 1
        final.append((f"{ident}#{seen[ident]}", True))
    if len(final) != len(set(final)):
        raise RuntimeError("upstream endpoints cannot be uniquely fingerprinted")
    return final


def rows_from(snap: dict) -> list[dict]:
    iso, rows = snap["generated"], []
    for model, raw in sorted(snap["endpoints"].items()):
        if isinstance(raw, dict) and raw.get("error"):
            rows.append(dict(zip(FIELDS, [iso, model, None, "poll-error",
                                          "poll-error", False, "unknown",
                                          None, None, None, None])))
            continue
        eps = raw.get("data", {}).get("endpoints", []) if isinstance(raw, dict) else []
        if not eps:
            rows.append(dict(zip(FIELDS, [iso, model, None, "catalog-no-endpoint",
                                          "catalog-no-endpoint", False, "idle",
                                          None, None, None, None])))
            continue
        for ep, (endpoint_id, ambiguous) in zip(eps, endpoint_identities(eps)):
            st, up30 = ep.get("status"), ep.get("uptime_last_30m")
            rows.append({
                "ts": iso, "model": model, "provider": ep.get("provider_name"),
                "endpoint_tag": ep.get("tag") or ep.get("name")
                or ep.get("provider_name"),
                "endpoint_id": endpoint_id,
                "identity_ambiguous": ambiguous,
                "state": state_of(st, up30), "status": st,
                "up5m": ep.get("uptime_last_5m"), "up30m": up30,
                "up1d": ep.get("uptime_last_1d"),
            })
    keys = [(r["model"], r["endpoint_id"] or r["endpoint_tag"]
             or f"provider:{r['provider']}") for r in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"duplicate endpoint identity in {iso}")
    return rows


class History:
    """Replays raw snapshots in order and accumulates the stateful artifacts.

    One snapshot at a time: feed() returns that snapshot's derived rows and
    advances incidents / last_seen / latest. Holding every snapshot in memory
    at once is what took the daily audit past the runner's RAM -- it was
    killed four days running once the archive passed ~2,500 snapshots -- and
    the state that actually has to persist between snapshots is a few
    thousand rows.
    """

    def __init__(self) -> None:
        self.incidents: list[dict] = []
        self.last_seen: dict = {}
        self.latest = None
        self.latest_transition_count = 0
        self.previous_snapshot_ts = None

    def feed(self, snap: dict) -> list[dict]:
        before = len(self.incidents)
        rows = rows_from(snap)
        current = {(r["model"], r["endpoint_id"] or r["endpoint_tag"]
                    or f"provider:{r['provider']}"): r
                   for r in rows}
        ambiguous_groups = {(r["model"], r["endpoint_tag"]) for r in rows
                            if r.get("identity_ambiguous")}
        last_seen = self.last_seen
        for key, old in list(last_seen.items()):
            if (old["model"], old.get("endpoint_tag")) in ambiguous_groups:
                del last_seen[key]
        for key, row in current.items():
            if row.get("identity_ambiguous"):
                continue
            old = last_seen.get(key)
            if old and old["state"] in STABLE and row["state"] in STABLE \
                    and old["state"] != row["state"] \
                    and "down" in (old["state"], row["state"]):
                previous_ts = old["ts"]
                gap = bool(self.previous_snapshot_ts
                           and previous_ts != self.previous_snapshot_ts)
                self.incidents.append({
                    "ts": row["ts"], "model": row["model"],
                    "provider": row["provider"], "endpoint_tag": row["endpoint_tag"],
                    "endpoint_id": row["endpoint_id"],
                    "from": old["state"], "to": row["state"],
                    "event": "down" if row["state"] == "down" else "recovered",
                    "up30m": row["up30m"],
                    "previous_ts": previous_ts,
                    "observation_gap": gap,
                    "minutes_since_last_seen": (
                        datetime.fromisoformat(row["ts"])
                        - datetime.fromisoformat(previous_ts)
                    ).total_seconds() / 60,
                })
            if row["state"] in STABLE:
                last_seen[key] = row
        self.previous_snapshot_ts = snap["generated"]
        self.latest = (snap, rows)
        self.latest_transition_count = len(self.incidents) - before
        return rows


def build_history(snapshots):
    """Pure raw-to-artifact transform; History is the streaming form of it."""
    history, by_day = History(), defaultdict(list)
    for snap in snapshots:
        by_day[snap["generated"][:10]].extend(history.feed(snap))
    return (by_day, history.incidents, history.last_seen, history.latest,
            history.latest_transition_count)


def iter_snapshots(paths):
    """Decode raw archives one at a time, in the order given."""
    for path in paths:
        with gzip.open(path, "rt") as f:
            yield json.load(f)


def last_seen_payload(last_seen: dict, generated: str) -> dict:
    return {
        "generated": generated,
        "note": "last observed state per endpoint; retained across observation gaps",
        "endpoints": sorted(({
            "ts": r["ts"], "model": r["model"], "provider": r["provider"],
            "endpoint_tag": r["endpoint_tag"], "endpoint_id": r["endpoint_id"],
            "state": r["state"],
        } for r in last_seen.values()), key=lambda r: (r["model"], r["endpoint_id"])),
    }


def latest_payload(latest, transitions_this_run: int) -> dict:
    snap, rows = latest
    counts = sum(r["state"] in ("down", "degraded") for r in rows)
    return {
        "generated": snap["generated"], "models_polled": len(snap["endpoints"]),
        "providers": len(snap.get("providers", {}).get("data", [])),
        "endpoint_count": len(rows), "down_or_degraded": counts,
        "transitions_this_run": transitions_this_run, "schema_version": 2,
        "endpoint_identity": "model + endpoint_id",
        "endpoints": [{k: r[k] for k in (
            "model", "provider", "endpoint_tag", "endpoint_id",
            "identity_ambiguous", "state", "up5m", "up30m")}
            for r in rows],
    }


def main() -> None:
    paths = sorted(RAW.glob("*/*.json.gz"))
    if not paths:
        raise SystemExit("no raw archives")
    DERIVED.mkdir(exist_ok=True)

    def flush(day: str, rows: list[dict]) -> None:
        with open(DERIVED / f"{day}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader(); w.writerows(rows)

    # A day's CSV is written as soon as the archive moves past that day. The
    # archive directory is the snapshot's own date, so sorted paths visit each
    # day exactly once; the guard turns any exception to that into a loud
    # failure instead of a silently overwritten day.
    history, day, buffered, total, seen_days = History(), None, [], 0, set()
    for snap in iter_snapshots(paths):
        this_day = snap["generated"][:10]
        if this_day != day:
            if day is not None:
                flush(day, buffered); buffered = []
            if this_day in seen_days:
                raise SystemExit(f"raw archive revisits {this_day} out of order")
            seen_days.add(this_day); day = this_day
        rows = history.feed(snap)
        buffered.extend(rows); total += len(rows)
    flush(day, buffered)

    STATUS.mkdir(exist_ok=True)
    (STATUS / "incidents.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in history.incidents))
    (STATUS / "last_seen.json").write_text(json.dumps(
        last_seen_payload(history.last_seen, history.latest[0]["generated"]), indent=1))
    (STATUS / "latest.json").write_text(json.dumps(
        latest_payload(history.latest, history.latest_transition_count), indent=1))
    print(f"rebuilt {len(paths)} snapshots, {total} rows, "
          f"{len(history.incidents)} transitions")


if __name__ == "__main__":
    main()
