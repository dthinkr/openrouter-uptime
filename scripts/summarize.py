#!/usr/bin/env python3
"""Regenerate the README front page from status/latest.json.

Renders: last-updated time, headline counts, and a table of every endpoint
currently down or degraded. Keeps the top of README (everything above the
AUTOGEN marker) intact.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = "<!-- AUTOGEN:STATUS -->"


def main() -> None:
    latest = json.loads((ROOT / "status" / "latest.json").read_text())
    eps = latest.get("endpoints", [])
    bad = sorted(
        (e for e in eps if e["state"] in ("down", "degraded")),
        key=lambda e: (e["state"] != "down", e["model"]))

    lines = [MARK, "",
             f"## Current status — {latest['generated']} UTC", "",
             f"- **{latest['models_polled']}** models polled, "
             f"**{latest['endpoint_count']}** inference endpoints",
             f"- **{latest['down_or_degraded']}** currently down or degraded",
             f"- **{latest.get('transitions_this_run', 0)}** state changes "
             f"in the last poll", ""]
    if bad:
        lines += ["| model | provider | state | uptime 5m | uptime 30m |",
                  "|---|---|---|---|---|"]
        for e in bad[:60]:
            u5 = f"{e['up5m']:.1f}%" if isinstance(e["up5m"], (int, float)) \
                else "—"
            u30 = f"{e['up30m']:.1f}%" if isinstance(e["up30m"], (int, float)) \
                else "—"
            lines.append(f"| `{e['model']}` | {e['provider']} | "
                         f"**{e['state']}** | {u5} | {u30} |")
        if len(bad) > 60:
            lines.append(f"| … | +{len(bad) - 60} more | | | |")
    else:
        lines.append("_All polled endpoints are up._")
    lines.append("")

    readme = ROOT / "README.md"
    head = readme.read_text().split(MARK)[0].rstrip() if readme.exists() else ""
    readme.write_text(head + "\n\n" + "\n".join(lines) + "\n")
    print(f"README updated: {len(bad)} down/degraded")


if __name__ == "__main__":
    main()
