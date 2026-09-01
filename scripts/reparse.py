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
import hashlib
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


def main(path: str) -> None:
    with gzip.open(path, "rt") as f:
        snap = json.load(f)
    iso = snap["generated"]
    w = csv.writer(sys.stdout)
    w.writerow(["ts", "model", "provider", "endpoint_tag", "endpoint_id",
                "identity_ambiguous", "state",
                "status", "up5m", "up30m", "up1d"])
    for slug, raw in sorted(snap["endpoints"].items()):
        if isinstance(raw, dict) and raw.get("error"):
            w.writerow([iso, slug, None, "poll-error", "poll-error", False, "unknown",
                        None, None, None, None])
            continue
        eps = raw.get("data", {}).get("endpoints", []) if isinstance(raw, dict) else []
        if not eps:
            w.writerow([iso, slug, None, "catalog-no-endpoint",
                        "catalog-no-endpoint", False, "idle", None, None, None, None])
            continue
        for ep, (endpoint_id, ambiguous) in zip(eps, endpoint_identities(eps)):
            st = ep.get("status")
            u30 = ep.get("uptime_last_30m")
            tag = ep.get("tag") or ep.get("name") or ep.get("provider_name")
            w.writerow([iso, slug, ep.get("provider_name"), tag, endpoint_id, ambiguous,
                        state_of(st, u30), st, ep.get("uptime_last_5m"),
                        u30, ep.get("uptime_last_1d")])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
