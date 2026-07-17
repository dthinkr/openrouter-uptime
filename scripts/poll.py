#!/usr/bin/env python3
"""Poll OpenRouter's public catalog and routing-endpoint health surfaces.

Keyless. Each run captures, verbatim, three public API surfaces:
  - /api/v1/models                     the full model catalog
  - /api/v1/providers                  provider metadata (HQ, ToS/privacy/
                                       status-page URLs). Until 2026-07-15 this
                                       was /api/frontend/all-providers, which
                                       also published data policies (training,
                                       prompt retention, moderation); upstream
                                       retired it without a keyless replacement.
  - /api/v1/models/{id}/endpoints      per inference-endpoint uptime/status

The complete raw responses are archived (ground truth); tidy tables and current
snapshots are derived from them and can always be rebuilt via reparse.py.

Writes per run:
  raw/<date>/<time>.json.gz     verbatim archive of everything above
  derived/<date>.csv            one row per endpoint (uptime readings)
  status/latest.json            current endpoint snapshot
  status/incidents.jsonl        endpoints crossing into/out of `down`
  status/models.json            live model catalog
  status/model_changes.jsonl    models added / removed
  status/providers.json         provider data policies
  status/provider_changes.jsonl provider policy / ToS changes
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"
STATUS = ROOT / "status"
RAW = ROOT / "raw"
API = "https://openrouter.ai/api/v1"
UA = {"User-Agent": "openrouter-uptime (github.com/dthinkr/openrouter-uptime)"}
WORKERS = 12
RETRIES = 3

# OpenRouter `status` health code: 0 healthy, -2 degraded, -5 down.
STATUS_DOWN, STATUS_DEGRADED = -5, -2
DEGRADED_BELOW, DOWN_AT = 98.0, 50.0


def get(url: str):
    last = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 best-effort poller
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def log_changes(path: Path, added, removed, iso, kind) -> None:
    if not (added or removed):
        return
    with open(path, "a", encoding="utf-8") as f:
        for i in sorted(added):
            f.write(json.dumps({"ts": iso, "event": f"{kind}_added",
                                "id": i}) + "\n")
        for i in sorted(removed):
            f.write(json.dumps({"ts": iso, "event": f"{kind}_removed",
                                "id": i}) + "\n")


def track_models(models_raw, iso) -> tuple[list[str], list[dict]]:
    data = models_raw["data"]
    # Model suffixes such as `:free` and `:thinking` are distinct catalog IDs.
    # Stripping them silently skipped variant-only models and queried a base ID
    # that did not always exist.
    slugs = sorted({m["id"] for m in data})
    catalog = sorted(({"id": m["id"], "name": m.get("name"),
                       "created": m.get("created"),
                       "context_length": m.get("context_length")}
                      for m in data), key=lambda m: m["id"])
    path = STATUS / "models.json"
    prev = {m["id"] for m in json.loads(path.read_text()).get("models", [])} \
        if path.exists() else set()
    now = {m["id"] for m in catalog}
    if prev:
        log_changes(STATUS / "model_changes.jsonl", now - prev, prev - now,
                    iso, "model")
    path.write_text(json.dumps({"generated": iso, "count": len(catalog),
                                "models": catalog}, indent=1))
    return slugs, catalog


def track_providers(prov_raw, iso) -> None:
    """Persist provider metadata; log additions, removals and policy changes.

    Upstream retired /api/frontend/all-providers in July 2026; the replacement
    /api/v1/providers no longer publishes `dataPolicy` or `moderationRequired`,
    so `data_policy` is null from then on (last-known values remain in the raw
    archives). A one-time `provider_policy_source_removed` event marks the
    break in the series. Both the retired and current response shapes are
    accepted so old raw archives can still be reparsed.
    """
    provs = sorted(({"slug": p.get("slug"), "name": p.get("name"),
                     "headquarters": p.get("headquarters"),
                     "data_policy": p.get("dataPolicy"),
                     "moderation_required": p.get("moderationRequired"),
                     "terms_of_service_url": p.get("terms_of_service_url"),
                     "privacy_policy_url": p.get("privacy_policy_url"),
                     "status_page": p.get("status_page_url")
                                      or p.get("statusPageUrl")}
                    for p in prov_raw["data"]), key=lambda p: p["slug"] or "")
    path = STATUS / "providers.json"
    prev = {p["slug"]: p for p in json.loads(path.read_text()).get(
        "providers", [])} if path.exists() else {}
    now = {p["slug"]: p for p in provs}
    log_changes(STATUS / "provider_changes.jsonl",
                set(now) - set(prev), set(prev) - set(now), iso, "provider")
    source_lost = bool(prev) \
        and any(p.get("data_policy") is not None for p in prev.values()) \
        and all(p["data_policy"] is None for p in now.values())
    with open(STATUS / "provider_changes.jsonl", "a", encoding="utf-8") as f:
        if source_lost:
            f.write(json.dumps({
                "ts": iso, "event": "provider_policy_source_removed",
                "note": "upstream retired /api/frontend/all-providers; "
                        "data_policy/moderation_required no longer published"
            }) + "\n")
        for slug in set(now) & set(prev):
            # policy edits on existing providers (only possible while both
            # snapshots still carry the retired dataPolicy object)
            if now[slug]["data_policy"] is not None \
                    and now[slug]["data_policy"] != prev[slug].get("data_policy"):
                f.write(json.dumps({"ts": iso, "event": "provider_policy_changed",
                                    "id": slug, "from": prev[slug]["data_policy"],
                                    "to": now[slug]["data_policy"]}) + "\n")
            # ToS / privacy / status-page URL edits. Fields absent from the
            # pre-migration snapshot have no baseline, so the migration run
            # itself logs nothing here.
            for field in ("terms_of_service_url", "privacy_policy_url",
                          "status_page"):
                if field not in prev[slug]:
                    continue
                if now[slug][field] != prev[slug][field]:
                    f.write(json.dumps({"ts": iso,
                                        "event": "provider_url_changed",
                                        "id": slug, "field": field,
                                        "from": prev[slug][field],
                                        "to": now[slug][field]}) + "\n")
    path.write_text(json.dumps({"generated": iso, "count": len(provs),
                                "providers": provs}, indent=1))


def fetch_endpoints(slug: str):
    try:
        raw = get(f"{API}/models/{slug}/endpoints")
    except Exception as e:  # noqa: BLE001
        return ([{"model": slug, "provider": None, "endpoint_tag": "poll-error",
                  "endpoint_id": "poll-error", "identity_ambiguous": False,
                  "status": None, "up5m": None, "up30m": None,
                  "up1d": None, "error": 1}], {"error": str(e)[:120]})
    eps = raw.get("data", {}).get("endpoints", [])
    endpoint_identities = make_endpoint_identities(eps)
    out = [{"model": slug, "provider": ep.get("provider_name"),
            # `tag` is human-readable but is not always unique. `endpoint_id`
            # adds a deterministic fingerprint only when duplicate tags exist.
            "endpoint_tag": endpoint_base(ep), "endpoint_id": endpoint_id,
            "identity_ambiguous": ambiguous,
            "status": ep.get("status"), "up5m": ep.get("uptime_last_5m"),
            "up30m": ep.get("uptime_last_30m"), "up1d": ep.get("uptime_last_1d"),
            "error": 0} for ep, (endpoint_id, ambiguous)
            in zip(eps, endpoint_identities)]
    if not out:
        out = [{"model": slug, "provider": None,
                "endpoint_tag": "catalog-no-endpoint",
                "endpoint_id": "catalog-no-endpoint", "identity_ambiguous": False,
                "status": None, "up5m": None, "up30m": None,
                "up1d": None, "error": 0}]
    return out, raw


def endpoint_base(ep) -> str:
    return str(ep.get("tag") or ep.get("name") or ep.get("provider_name")
               or "unknown")


def endpoint_fingerprint(ep) -> str:
    """Disambiguate simultaneous duplicate tags; never used longitudinally."""
    signature = {
        "tag": endpoint_base(ep),
        "name": ep.get("name"),
        "model_id": ep.get("model_id"),
        "provider_name": ep.get("provider_name"),
        "pricing": ep.get("pricing"),
        "quantization": ep.get("quantization"),
        "context_length": ep.get("context_length"),
        "max_completion_tokens": ep.get("max_completion_tokens"),
        "max_prompt_tokens": ep.get("max_prompt_tokens"),
        "supported_parameters": sorted(ep.get("supported_parameters") or []),
        "supports_implicit_caching": ep.get("supports_implicit_caching"),
    }
    raw = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def make_endpoint_identities(eps) -> list[tuple[str, bool]]:
    from collections import Counter
    bases = [endpoint_base(ep) for ep in eps]
    counts = Counter(bases)
    ids = [(base, False) if counts[base] == 1
           else (f"{base}#{endpoint_fingerprint(ep)}", True)
           for base, ep in zip(bases, eps)]
    if len(ids) != len(set(ids)):
        raise RuntimeError("upstream endpoints cannot be uniquely fingerprinted")
    return ids


def make_endpoint_ids(eps) -> list[str]:
    """Compatibility helper used by tests and one-off callers."""
    return [endpoint_id for endpoint_id, _ in make_endpoint_identities(eps)]


def endpoint_identity(row) -> tuple[str, str]:
    """Stable identity for one routing endpoint.

    Provider name alone is not unique: a provider may publish multiple tags for
    the same model. Falling back to provider only supports pre-v2 snapshots.
    """
    ident = row.get("endpoint_id") or row.get("endpoint_tag") \
        or f"provider:{row.get('provider')}"
    return str(row.get("model")), str(ident)


def validate_unique_endpoints(rows) -> None:
    keys = [endpoint_identity(r) for r in rows]
    if len(keys) != len(set(keys)):
        from collections import Counter
        dupes = [k for k, n in Counter(keys).items() if n > 1]
        raise RuntimeError(f"duplicate endpoint identities: {dupes[:10]}")


def state_of(row) -> str:
    if row.get("error"):
        return "unknown"
    st, up30 = row.get("status"), row.get("up30m")
    if st == STATUS_DOWN or (up30 is not None and up30 < DOWN_AT):
        return "down"
    if st == STATUS_DEGRADED or (up30 is not None and up30 < DEGRADED_BELOW):
        return "degraded"
    if up30 is None:
        return "idle"
    return "up"


def main() -> None:
    ts = float(os.environ.get("POLL_TS", "0")) or time.time()
    # Strip microseconds once: `generated` is second-precision, so every
    # derived duration (e.g. minutes_since_last_seen) must be computed from a
    # second-aligned `now`, otherwise incremental incidents drift from the
    # raw-replayed history and audit's exact-match check fails.
    now = datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0)
    iso = now.isoformat()
    for d in (DERIVED, STATUS, RAW):
        d.mkdir(exist_ok=True)

    models_raw = get(f"{API}/models")
    providers_raw = get(f"{API}/providers")
    slugs, _ = track_models(models_raw, iso)
    track_providers(providers_raw, iso)

    rows, endpoints_raw = [], {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for slug, (eps, raw) in zip(slugs, ex.map(fetch_endpoints, slugs)):
            rows.extend(eps)
            endpoints_raw[slug] = raw
    for r in rows:
        r["state"] = state_of(r)
    # Stop before writing a corrupted snapshot if the upstream schema changes.
    validate_unique_endpoints(rows)

    # 0. verbatim raw archive (ground truth)
    run_dir = RAW / f"{now:%Y-%m-%d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(run_dir / f"{now:%H%M%S}.json.gz", "wt") as f:
        json.dump({"generated": iso, "schema_version": 2,
                   "model_query": "exact_catalog_id",
                   "endpoint_identity": "model + endpoint_id",
                   "providers_source": f"{API}/providers",
                   "models": models_raw,
                   "providers": providers_raw, "endpoints": endpoints_raw}, f)

    # 1. derived readings CSV
    day = DERIVED / f"{now:%Y-%m-%d}.csv"
    new = not day.exists()
    with open(day, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "model", "provider", "endpoint_tag", "endpoint_id",
                        "identity_ambiguous",
                        "state", "status",
                        "up5m", "up30m", "up1d"])
        for r in rows:
            w.writerow([iso, r["model"], r["provider"], r["endpoint_tag"],
                        r["endpoint_id"], r["identity_ambiguous"],
                        r["state"], r["status"],
                        r["up5m"], r["up30m"], r["up1d"]])

    # 2. incident log (crossing the DOWN boundary only). Keep last-seen state
    # across observation gaps; otherwise a disappearing endpoint can create two
    # consecutive `down` edges with an unrecorded recovery between them.
    prev_path = STATUS / "latest.json"
    previous_snapshot_ts = None
    if prev_path.exists():
        previous_snapshot_ts = json.loads(prev_path.read_text()).get("generated")
    last_seen_path = STATUS / "last_seen.json"
    if last_seen_path.exists():
        last_seen_rows = json.loads(last_seen_path.read_text()).get("endpoints", [])
    elif prev_path.exists():
        prior = json.loads(prev_path.read_text())
        last_seen_rows = [dict(r, ts=prior.get("generated"))
                          for r in prior.get("endpoints", [])]
    else:
        last_seen_rows = []
    last_seen = {endpoint_identity(r): r for r in last_seen_rows}
    ambiguous_groups = {(r["model"], r["endpoint_tag"]) for r in rows
                        if r.get("identity_ambiguous")}
    for key, old in list(last_seen.items()):
        if (old["model"], old.get("endpoint_tag")) in ambiguous_groups:
            del last_seen[key]
    transitions, stable = 0, {"up", "degraded", "down"}
    with open(STATUS / "incidents.jsonl", "a", encoding="utf-8") as f:
        for r in rows:
            if r.get("identity_ambiguous"):
                continue
            old, nowst = last_seen.get(endpoint_identity(r)), r["state"]
            was = old.get("state") if old else None
            if was in stable and nowst in stable and was != nowst \
                    and "down" in (was, nowst):
                previous_ts = old.get("ts")
                gap = bool(previous_snapshot_ts and previous_ts != previous_snapshot_ts)
                gap_minutes = ((now - datetime.fromisoformat(previous_ts)).total_seconds() / 60
                               if previous_ts else None)
                f.write(json.dumps({
                    "ts": iso, "model": r["model"], "provider": r["provider"],
                    "endpoint_tag": r["endpoint_tag"],
                    "endpoint_id": r["endpoint_id"],
                    "from": was, "to": nowst,
                    "event": "down" if nowst == "down" else "recovered",
                    "up30m": r["up30m"], "previous_ts": previous_ts,
                    "observation_gap": gap, "minutes_since_last_seen": gap_minutes,
                }) + "\n")
                transitions += 1
            if r["state"] in stable:
                last_seen[endpoint_identity(r)] = {
                    "ts": iso, "model": r["model"], "provider": r["provider"],
                    "endpoint_tag": r["endpoint_tag"], "endpoint_id": r["endpoint_id"],
                    "state": r["state"],
                }

    # 3. latest snapshot
    down = [r for r in rows if r["state"] in ("down", "degraded")]
    prev_path.write_text(json.dumps({
        "generated": iso, "models_polled": len(slugs),
        "providers": providers_raw and len(providers_raw["data"]),
        "endpoint_count": len(rows), "down_or_degraded": len(down),
        "transitions_this_run": transitions,
        "schema_version": 2,
        "endpoint_identity": "model + endpoint_id",
        "endpoints": [{"model": r["model"], "provider": r["provider"],
                       "endpoint_tag": r["endpoint_tag"],
                       "endpoint_id": r["endpoint_id"],
                       "identity_ambiguous": r["identity_ambiguous"],
                       "state": r["state"], "up5m": r["up5m"],
                       "up30m": r["up30m"]} for r in rows]}, indent=1))
    last_seen_path.write_text(json.dumps({
        "generated": iso,
        "note": "last observed state per endpoint; retained across observation gaps",
        "endpoints": sorted(last_seen.values(),
                            key=lambda r: (r["model"], r["endpoint_id"])),
    }, indent=1))
    print(f"{iso}  models={len(slugs)} providers={len(providers_raw['data'])} "
          f"endpoints={len(rows)} down/degraded={len(down)} "
          f"transitions={transitions}")


if __name__ == "__main__":
    main()
