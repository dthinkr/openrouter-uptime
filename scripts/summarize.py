#!/usr/bin/env python3
"""Regenerate the README status block from status/latest.json.

Keeps it lean: headline counts plus a short list of endpoints that are fully
`down` (not the long degraded tail). Full detail lives in status/latest.json.
Everything above the AUTOGEN marker in README.md is left untouched.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = "<!-- AUTOGEN:STATUS -->"
DOWN_CAP = 15


def main() -> None:
    latest = json.loads((ROOT / "status" / "latest.json").read_text())
    eps = latest.get("endpoints", [])
    counts = Counter(e["state"] for e in eps)
    down = sorted((e for e in eps if e["state"] == "down"),
                  key=lambda e: e["model"])

    lines = [MARK, "",
             f"## Current status ({latest['generated']} UTC)", "",
             f"{latest['models_polled']} models polled, "
             f"{latest['endpoint_count']} inference endpoints:",
             f"up {counts.get('up', 0)}, degraded {counts.get('degraded', 0)}, "
             f"down {counts.get('down', 0)}, idle {counts.get('idle', 0)}.", ""]

    if down:
        lines.append(f"Currently down ({len(down)}):")
        lines.append("")
        lines.append("| model | provider | 30m uptime | 5m uptime |")
        lines.append("|---|---|---|---|")
        for e in down[:DOWN_CAP]:
            u30 = (f"{e['up30m']:.0f}%" if isinstance(e["up30m"], (int, float))
                   else "n/a")
            u5 = (f"{e['up5m']:.0f}%" if isinstance(e["up5m"], (int, float))
                  else "n/a")
            lines.append(f"| `{e['model']}` | {e['provider']} | {u30} | {u5} |")
        if len(down) > DOWN_CAP:
            lines.append(f"| plus {len(down) - DOWN_CAP} more | | | |")
    else:
        lines.append("No endpoints are fully down.")
    lines += ["", "Full snapshot: [`status/latest.json`](status/latest.json). "
              "Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).",
              ""]

    readme = ROOT / "README.md"
    head = readme.read_text().split(MARK)[0].rstrip() if readme.exists() else ""
    readme.write_text(head + "\n\n" + "\n".join(lines) + "\n")
    print(f"README updated: down={len(down)}, degraded={counts.get('degraded',0)}")


if __name__ == "__main__":
    main()
