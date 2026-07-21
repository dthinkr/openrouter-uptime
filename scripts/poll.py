#!/usr/bin/env python3
"""Poll OpenRouter for the live state of every model and provider.

Keyless. Each run captures, verbatim, three public API surfaces:
  - /api/v1/models                     the full model catalog. On fetch failure
                                       the last good snapshot is reused, so
                                       uptime readings never stop; catalog
                                       tracking (adds/removes) resumes on
                                       recovery.
  - /api/v1/providers                  provider metadata (HQ, ToS/privacy/
                                       status-page URLs). Best-effort: fetch
                                       failures are logged and carried forward,
                                       never a reason to skip uptime readings.
                                       Until 2026-07-15 this was
                                       /api/frontend/all-providers, which also
                                       published data policies (training,
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


def last_change_event(path: Path):
    """Last event in a change log, or None. Used to log provider-fetch
    outages only at the ok->error and error->ok edges instead of every run."""
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1]) if lines else None


def track_models(models_raw, iso) -> tuple[list[str], list[dict]]:
    data = models_raw["data"]
    slugs = sorted({m["id"].split(":")[0] for m in data})
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
        return ([{"model": slug, "provider": None, "status": None, "up5m": None,
                  "up30m": None, "up1d": None, "error": 1}], {"error": str(e)[:120]})
    out = [{"model": slug, "provider": ep.get("provider_name"),
            "status": ep.get("status"), "up5m": ep.get("uptime_last_5m"),
            "up30m": ep.get("uptime_last_30m"), "up1d": ep.get("uptime_last_1d"),
            "error": 0} for ep in raw.get("data", {}).get("endpoints", [])]
    if not out:
        out = [{"model": slug, "provider": None, "status": None, "up5m": None,
                "up30m": None, "up1d": None, "error": 0}]
    return out, raw


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
    now = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = now.replace(microsecond=0).isoformat()
    for d in (DERIVED, STATUS, RAW):
        d.mkdir(exist_ok=True)

    # Models catalog: on fetch failure fall back to the last good snapshot so
    # an upstream wobble pauses catalog *tracking* (additions/removals resume
    # on recovery) instead of the uptime readings. Only a cold start with no
    # prior snapshot is a hard failure.
    models_raw, models_error = None, None
    try:
        models_raw = get(f"{API}/models")
    except Exception as e:  # noqa: BLE001 best-effort poller
        models_error = str(e)[:200]
    mchanges_path = STATUS / "model_changes.jsonl"
    m_last = (last_change_event(mchanges_path) or {}).get("event")
    if models_error is not None:
        catalog_path = STATUS / "models.json"
        prev_catalog = json.loads(catalog_path.read_text()).get("models", []) \
            if catalog_path.exists() else []
        if not prev_catalog:
            raise RuntimeError("models catalog fetch failed and no prior "
                               f"snapshot to fall back on: {models_error}")
        if m_last != "model_fetch_error":
            with open(mchanges_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": iso, "event": "model_fetch_error",
                                    "error": models_error}) + "\n")
        slugs = sorted({m["id"].split(":")[0] for m in prev_catalog})
    else:
        if m_last == "model_fetch_error":
            with open(mchanges_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": iso,
                                    "event": "model_fetch_recovered"}) + "\n")
        slugs, _ = track_models(models_raw, iso)
    # Providers is a nice-to-have sidecar: a failure here must not stop the
    # uptime readings (it did for two days when all-providers was retired).
    # On failure keep polling, leave providers.json at its last good snapshot,
    # and record the outage in the change log at its edges only.
    providers_raw, providers_error = None, None
    try:
        providers_raw = get(f"{API}/providers")
    except Exception as e:  # noqa: BLE001 best-effort poller
        providers_error = str(e)[:200]
    changes_path = STATUS / "provider_changes.jsonl"
    last_event = (last_change_event(changes_path) or {}).get("event")
    if providers_error is not None:
        if last_event != "provider_fetch_error":
            with open(changes_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": iso, "event": "provider_fetch_error",
                                    "error": providers_error}) + "\n")
    else:
        if last_event == "provider_fetch_error":
            with open(changes_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": iso,
                                    "event": "provider_fetch_recovered"}) + "\n")
        track_providers(providers_raw, iso)

    rows, endpoints_raw = [], {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for slug, (eps, raw) in zip(slugs, ex.map(fetch_endpoints, slugs)):
            rows.extend(eps)
            endpoints_raw[slug] = raw
    for r in rows:
        r["state"] = state_of(r)

    # 0. verbatim raw archive (ground truth)
    run_dir = RAW / f"{now:%Y-%m-%d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(run_dir / f"{now:%H%M%S}.json.gz", "wt") as f:
        json.dump({"generated": iso, "providers_source": f"{API}/providers",
                   "models": models_raw if models_raw is not None
                            else {"error": models_error},
                   "providers": providers_raw if providers_raw is not None
                                else {"error": providers_error},
                   "endpoints": endpoints_raw}, f)

    # 1. derived readings CSV
    day = DERIVED / f"{now:%Y-%m-%d}.csv"
    new = not day.exists()
    with open(day, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "model", "provider", "state", "status",
                        "up5m", "up30m", "up1d"])
        for r in rows:
            w.writerow([iso, r["model"], r["provider"], r["state"], r["status"],
                        r["up5m"], r["up30m"], r["up1d"]])

    # 2. incident log (crossing the DOWN boundary only)
    prev_path = STATUS / "latest.json"
    prev = {(r["model"], r["provider"]): r["state"] for r in
            json.loads(prev_path.read_text()).get("endpoints", [])} \
        if prev_path.exists() else {}
    transitions, stable = 0, {"up", "degraded", "down"}
    with open(STATUS / "incidents.jsonl", "a", encoding="utf-8") as f:
        for r in rows:
            was, nowst = prev.get((r["model"], r["provider"])), r["state"]
            if was in stable and nowst in stable and was != nowst \
                    and "down" in (was, nowst):
                f.write(json.dumps({
                    "ts": iso, "model": r["model"], "provider": r["provider"],
                    "from": was, "to": nowst,
                    "event": "down" if nowst == "down" else "recovered",
                    "up30m": r["up30m"]}) + "\n")
                transitions += 1

    # 3. latest snapshot
    down = [r for r in rows if r["state"] in ("down", "degraded")]
    prev_path.write_text(json.dumps({
        "generated": iso, "models_polled": len(slugs),
        "providers": providers_raw and len(providers_raw["data"]),
        "endpoint_count": len(rows), "down_or_degraded": len(down),
        "transitions_this_run": transitions,
        "endpoints": [{"model": r["model"], "provider": r["provider"],
                       "state": r["state"], "up5m": r["up5m"],
                       "up30m": r["up30m"]} for r in rows]}, indent=1))
    print(f"{iso}  models={len(slugs)} "
          f"providers={providers_raw and len(providers_raw['data'])} "
          f"endpoints={len(rows)} down/degraded={len(down)} "
          f"transitions={transitions}")


if __name__ == "__main__":
    main()
