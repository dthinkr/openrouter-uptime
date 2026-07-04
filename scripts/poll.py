#!/usr/bin/env python3
"""Poll OpenRouter for the live status of EVERY model's inference endpoints.

Keyless: uses only the public OpenRouter API. Discovers the full model list
dynamically each run, then fetches per-endpoint uptime/status.

Writes, per run:
  data/<UTC-date>.csv        append one row per (model, provider) endpoint
  status/latest.json         full current snapshot (overwritten)
  status/incidents.jsonl     append a line whenever an endpoint's state flips
                             (up<->down<->degraded) vs the previous snapshot

No secrets, no external deps beyond the Python stdlib.
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
DATA = ROOT / "data"
STATUS = ROOT / "status"
RAW = ROOT / "raw"
API = "https://openrouter.ai/api/v1"
UA = {"User-Agent": "openrouter-uptime (github.com/OWNER/openrouter-uptime)"}
WORKERS = 12
RETRIES = 3

# OpenRouter's own `status` health code: 0 = healthy, -2 = degraded,
# -5 = down (observed encoding). We combine it with the 30-min uptime.
# A null uptime means the endpoint had no recent traffic (idle) — not a fault.
STATUS_DOWN = -5
STATUS_DEGRADED = -2
DEGRADED_BELOW = 98.0   # up30m in [DOWN_AT, DEGRADED_BELOW) -> degraded
DOWN_AT = 50.0          # up30m below this -> down


def get(url: str):
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - best-effort poller
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def track_catalog(catalog: list[dict], iso: str) -> None:
    """Persist the live model catalog and log additions/removals."""
    cat_path = STATUS / "models.json"
    prev_ids = set()
    if cat_path.exists():
        prev_ids = {m["id"] for m in json.loads(cat_path.read_text())
                    .get("models", [])}
    now_ids = {m["id"] for m in catalog}
    added, removed = now_ids - prev_ids, prev_ids - now_ids
    if (added or removed) and prev_ids:
        with open(STATUS / "model_changes.jsonl", "a") as f:
            for mid in sorted(added):
                f.write(json.dumps({"ts": iso, "event": "added",
                                    "id": mid}) + "\n")
            for mid in sorted(removed):
                f.write(json.dumps({"ts": iso, "event": "removed",
                                    "id": mid}) + "\n")
    cat_path.write_text(json.dumps(
        {"generated": iso, "count": len(catalog), "models": catalog}, indent=1))


def fetch_endpoints(slug: str) -> tuple[list[dict], object]:
    """Return (parsed_rows, raw_json). raw_json is archived verbatim so the
    dataset can always be re-derived if this parser is ever wrong."""
    try:
        raw = get(f"{API}/models/{slug}/endpoints")
    except Exception as e:  # noqa: BLE001
        return ([{"model": slug, "provider": None, "status": None,
                  "up5m": None, "up30m": None, "up1d": None, "error": 1}],
                {"error": str(e)[:120]})
    out = []
    for ep in raw.get("data", {}).get("endpoints", []):
        out.append({
            "model": slug,
            "provider": ep.get("provider_name"),
            "status": ep.get("status"),
            "up5m": ep.get("uptime_last_5m"),
            "up30m": ep.get("uptime_last_30m"),
            "up1d": ep.get("uptime_last_1d"),
            "error": 0,
        })
    if not out:
        out.append({"model": slug, "provider": None, "status": None,
                    "up5m": None, "up30m": None, "up1d": None, "error": 0})
    return out, raw


def state_of(row: dict) -> str:
    if row.get("error"):
        return "unknown"
    st, up30 = row.get("status"), row.get("up30m")
    if st == STATUS_DOWN or (up30 is not None and up30 < DOWN_AT):
        return "down"
    if st == STATUS_DEGRADED or (up30 is not None and up30 < DEGRADED_BELOW):
        return "degraded"
    if up30 is None:
        return "idle"          # no recent traffic — not a fault
    return "up"


def main() -> None:
    ts = float(os.environ.get("POLL_TS", "0")) or time.time()
    now = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = now.replace(microsecond=0).isoformat()

    STATUS.mkdir(exist_ok=True)
    models_raw = get(f"{API}/models")
    slugs = sorted({m["id"].split(":")[0] for m in models_raw["data"]})
    catalog = sorted(
        ({"id": m["id"], "name": m.get("name"), "created": m.get("created"),
          "context_length": m.get("context_length")}
         for m in models_raw["data"]), key=lambda m: m["id"])
    track_catalog(catalog, iso)

    rows: list[dict] = []
    endpoints_raw: dict[str, object] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for slug, (eps, raw) in zip(slugs, ex.map(fetch_endpoints, slugs)):
            rows.extend(eps)
            endpoints_raw[slug] = raw
    for r in rows:
        r["state"] = state_of(r)

    DATA.mkdir(exist_ok=True)
    STATUS.mkdir(exist_ok=True)

    # 0. archive the RAW API responses verbatim (ground truth; gzipped).
    #    If any parsing here is ever wrong, everything re-derives from these.
    run_dir = RAW / f"{now:%Y-%m-%d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(run_dir / f"{now:%H%M%S}.json.gz", "wt") as f:
        json.dump({"generated": iso, "models": models_raw,
                   "endpoints": endpoints_raw}, f)

    # 1. append compact rows to today's CSV
    day_file = DATA / f"{now:%Y-%m-%d}.csv"
    new = not day_file.exists()
    with open(day_file, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "model", "provider", "state",
                        "status", "up5m", "up30m", "up1d"])
        for r in rows:
            w.writerow([iso, r["model"], r["provider"], r["state"],
                        r["status"], r["up5m"], r["up30m"], r["up1d"]])

    # 2. transition log vs previous snapshot
    prev_path = STATUS / "latest.json"
    prev = {}
    if prev_path.exists():
        for r in json.loads(prev_path.read_text()).get("endpoints", []):
            prev[(r["model"], r["provider"])] = r["state"]
    # an "incident" line is logged only when an endpoint crosses the DOWN
    # boundary (starts or ends an outage) — not for every degraded flicker.
    inc_path = STATUS / "incidents.jsonl"
    transitions = 0
    stable = {"up", "degraded", "down"}
    with open(inc_path, "a") as f:
        for r in rows:
            key = (r["model"], r["provider"])
            was, nowst = prev.get(key), r["state"]
            if was not in stable or nowst not in stable or was == nowst:
                continue
            if "down" in (was, nowst):     # outage start or recovery only
                f.write(json.dumps({
                    "ts": iso, "model": r["model"], "provider": r["provider"],
                    "from": was, "to": nowst,
                    "event": "down" if nowst == "down" else "recovered",
                    "up30m": r["up30m"]}) + "\n")
                transitions += 1

    # 3. overwrite latest snapshot (the "endpoints" list feeds next run's diff)
    down = [r for r in rows if r["state"] in ("down", "degraded")]
    prev_path.write_text(json.dumps({
        "generated": iso, "models_polled": len(slugs),
        "endpoint_count": len(rows), "down_or_degraded": len(down),
        "transitions_this_run": transitions,
        "endpoints": [{"model": r["model"], "provider": r["provider"],
                       "state": r["state"], "up5m": r["up5m"],
                       "up30m": r["up30m"]} for r in rows],
    }, indent=1))

    print(f"{iso}  models={len(slugs)} endpoints={len(rows)} "
          f"down/degraded={len(down)} transitions={transitions}")


if __name__ == "__main__":
    main()
