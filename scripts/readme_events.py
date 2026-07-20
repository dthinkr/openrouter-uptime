#!/usr/bin/env python3
"""Regenerate the README "Systemic events" block from status/*_changes.jsonl.

Single-model adds/removals and per-endpoint outages are noise; this surfaces
only fleet-level signals:

  - batch model additions / removals (same poll run, >= BATCH_MIN models)
  - catalog or providers fetch outages and recoveries
  - provider exits (a provider leaving the platform entirely)
  - upstream schema breaks (e.g. the data-policy source being retired)
  - provider ToS / privacy / status-page URL edits

The block is fully rebuilt every run between AUTOGEN:EVENTS markers, so the
README needs no manual maintenance. run summarize.py first: this script
re-injects its section into the status block summarize.py writes.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "status"
MARK_BEGIN = "<!-- AUTOGEN:EVENTS:BEGIN -->"
MARK_END = "<!-- AUTOGEN:EVENTS:END -->"
STATUS_MARK = "<!-- AUTOGEN:STATUS -->"
BATCH_MIN = 3          # same-run model adds/removals to count as a batch
MAX_ITEMS = 8          # individual models listed per batch before folding
MAX_SECTION_EVENTS = 12  # most recent systemic events shown in README


def load(name: str) -> list[dict]:
    path = STATUS / name
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def short_ts(ts: str) -> str:
    return ts[:16].replace("T", " ")


def fmt_models(ids: list[str]) -> str:
    shown = ", ".join(f"`{i}`" for i in ids[:MAX_ITEMS])
    if len(ids) > MAX_ITEMS:
        shown += f", +{len(ids) - MAX_ITEMS} more"
    return shown


def collect() -> list[tuple[str, str]]:
    """Return (ts, markdown line) pairs, oldest first."""
    out: list[tuple[str, str]] = []

    # --- model catalog: batch adds/removals + fetch outages -------------------
    by_ts: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in load("model_changes.jsonl"):
        ev, ts = e["event"], e["ts"]
        if ev in ("model_added", "model_removed"):
            by_ts[(ts, ev)].append(e["id"])
        elif ev == "model_fetch_error":
            out.append((ts, f"**{short_ts(ts)}** — model catalog fetch failed: "
                            f"`{e.get('error', '?')}`; uptime readings continued "
                            f"against the last good catalog."))
        elif ev == "model_fetch_recovered":
            out.append((ts, f"**{short_ts(ts)}** — model catalog fetch recovered."))
    for (ts, ev), ids in sorted(by_ts.items()):
        if len(ids) >= BATCH_MIN:
            what = "removed from" if ev == "model_removed" else "added to"
            out.append((ts, f"**{short_ts(ts)}** — **{len(ids)} models "
                            f"{what} the catalog in one poll**: "
                            f"{fmt_models(sorted(ids))}."))

    # --- providers ------------------------------------------------------------
    for e in load("provider_changes.jsonl"):
        ev, ts = e["event"], e["ts"]
        if ev == "provider_removed":
            out.append((ts, f"**{short_ts(ts)}** — provider `{e['id']}` left "
                            f"the platform."))
        elif ev == "provider_fetch_error":
            out.append((ts, f"**{short_ts(ts)}** — providers fetch failed: "
                            f"`{e.get('error', '?')}`; last good provider "
                            f"snapshot kept."))
        elif ev == "provider_fetch_recovered":
            out.append((ts, f"**{short_ts(ts)}** — providers fetch recovered."))
        elif ev == "provider_policy_source_removed":
            note = e.get("note", "upstream stopped publishing data policies")
            out.append((ts, f"**{short_ts(ts)}** — **schema break**: {note}."))
        elif ev == "provider_url_changed":
            field = e.get("field", "url").replace("_", " ")
            out.append((ts, f"**{short_ts(ts)}** — provider `{e['id']}` "
                            f"changed its {field}."))

    out.sort(key=lambda x: x[0])
    return out


def render_block() -> list[str]:
    events = collect()
    lines = [MARK_BEGIN, "", "### Systemic events",
             "_Fleet-level changes extracted from the change logs every run; "
             "per-model churn is omitted._", ""]
    if not events:
        lines.append("None recorded yet.")
    else:
        for ts, line in events[-MAX_SECTION_EVENTS:]:
            lines.append(f"- {line}")
    lines += ["", "Full logs: [`status/model_changes.jsonl`]"
              "(status/model_changes.jsonl), "
              "[`status/provider_changes.jsonl`](status/provider_changes.jsonl).",
              "", MARK_END, ""]
    return lines


def inject(text: str, block: list[str]) -> str:
    """Replace an existing marked block, or append one at the end."""
    rendered = "\n".join(block)
    if MARK_BEGIN in text and MARK_END in text:
        head = text.split(MARK_BEGIN)[0].rstrip()
        tail = text.split(MARK_END, 1)[1].strip("\n")
        return head + "\n\n" + rendered + ("\n\n" + tail + "\n" if tail else "\n")
    return text.rstrip() + "\n\n" + rendered + "\n"


def main() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text()
    block = render_block()

    if STATUS_MARK in text:
        # summarize.py owns everything below the status marker and runs first;
        # re-inject the events section into what it wrote.
        head, status_section = text.split(STATUS_MARK, 1)
        status_section = inject(status_section, block)
        text = head + STATUS_MARK + status_section
    else:
        text = inject(text, block)

    readme.write_text(text)
    n = len(collect())
    shown = min(n, MAX_SECTION_EVENTS)
    print(f"README systemic events: {shown} shown ({n} total)")


if __name__ == "__main__":
    main()
