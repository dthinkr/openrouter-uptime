#!/usr/bin/env python3
"""Render the README charts from the derived data. Stdlib only.

Two figures, each written as a light/dark pair for GitHub's <picture>:

  status/strip-{light,dark}.svg      per-provider status strip (6-hour cells)
                                     sharing a time axis
                                     with the sampling-coverage strip -- every
                                     tick on the bottom row is one actual poll
  status/providers-{light,dark}.svg  per-provider day-scale trend from up1d,
                                     the one column whose 24-hour window
                                     survives sparse sampling

Ground rules, learned the hard way in this repo: the x axis is wall-clock
time, never poll index; windows with no observation are hatched, never
interpolated; idle is drawn as a neutral, because no traffic is not a fault.

Sizing is deliberate. GitHub renders README images into a column roughly
830 px wide and scales the SVG to fit, so a viewBox much wider than that
shrinks every glyph below legibility. Both figures are laid out to land near
1:1 at that width; widen the cells rather than the canvas if more room is
needed.

Runs in the daily publish workflow, not on the poll path -- it scans two
weeks of derived CSVs, and the collection path must carry no work that grows
with the dataset.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"
STATUS = ROOT / "status"

WINDOW_DAYS = 14
CELL_HOURS = 6
TOP_PROVIDERS = 8

# Shared page geometry. Both figures stack in the same README column, so they
# must share a canvas width and, more importantly, the same left and right
# content edges -- otherwise the provider labels of one sit under the plot
# area of the other and the pair reads as two unrelated images.
CANVAS_W = 814        # ~1:1 against GitHub's readme column
LABEL_W = 132         # x where the plot area starts, both figures
RIGHT_W = 78          # reserved right gutter, both figures
PLOT_W = CANVAS_W - LABEL_W - RIGHT_W
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    # calibrated against GitHub's readme backgrounds: #ffffff / #0d1117
    "light": {"ink": "#1f2328", "soft": "#59636e", "faint": "#818b98",
              "rule": "#d1d9e0", "up": "#1a9862", "idle": "#b9c3c0",
              "deg": "#b98300", "down": "#cf4444", "gap": "#9aa4a1",
              "accent": "#4a5bc4"},
    "dark":  {"ink": "#e6edf3", "soft": "#8b949e", "faint": "#6e7681",
              "rule": "#30363d", "up": "#3fb884", "idle": "#3d4a47",
              "deg": "#d9a63e", "down": "#e36a6a", "gap": "#5c6a66",
              "accent": "#93a0f2"},
}

def cell_shares(n_up: int, n_idle: int, n_deg: int, n_down: int):
    """(impaired_share, down_share) for one provider-window."""
    total = n_up + n_idle + n_deg + n_down
    if total == 0:
        return None
    return ((n_deg + n_down) / total, n_down / total)


def classify(shares, baseline: float) -> str:
    """Colour = deviation from the row's own 14-day norm.

    Chronic impairment differs by an order of magnitude across providers
    (Azure sits near 2%, DeepInfra near 20%), so any absolute threshold
    either paints the tail providers as a permanent amber wall or hides a
    2x spike at the clean ones. Each row is therefore judged against its
    own median impaired share, which is printed on the row so the baseline
    is disclosed rather than hidden: amber means at least five points worse
    than usual for THIS provider, red means a majority of its endpoints are
    hard-down -- that is severe at any baseline. Idle counts as healthy.
    """
    if shares is None:
        return "idle"
    impaired, down = shares
    if down > 0.5:
        return "down"
    if impaired > max(baseline + 0.05, 0.05):
        return "degraded"
    return "up"


def load_window():
    latest = json.loads((STATUS / "latest.json").read_text())
    end = datetime.fromisoformat(latest["generated"])
    start = datetime.combine(end.date() - timedelta(days=WINDOW_DAYS - 1),
                             datetime.min.time(), tzinfo=timezone.utc)

    counts: dict[str, int] = {}
    for e in latest["endpoints"]:
        if e.get("provider"):
            counts[e["provider"]] = counts.get(e["provider"], 0) + 1
    top = [p for p, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:TOP_PROVIDERS]]

    day = start.date()
    rows = []
    while day <= end.date():
        f = DERIVED / f"{day.isoformat()}.csv"
        if f.exists():
            with f.open(newline="", encoding="utf-8") as fh:
                rows.extend(csv.DictReader(fh))
        day += timedelta(days=1)

    ts_cache: dict[str, datetime] = {}
    for r in rows:
        t = r["ts"]
        if t not in ts_cache:
            dt = datetime.fromisoformat(t)
            ts_cache[t] = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    polls = sorted(t for t in ts_cache.values() if start <= t <= end)

    return latest, start, end, top, rows, ts_cache, polls


def build_cells(start, end, top, rows, ts_cache):
    """cells[provider_or_None][col] -> (impaired, down) | None; plus medians."""
    span_h = (end - start).total_seconds() / 3600.0
    ncols = int(span_h // CELL_HOURS) + 1
    acc: dict[str | None, list[list[int] | None]] = {
        p: [None] * ncols for p in [None, *top]}
    idx = {"up": 0, "idle": 1, "degraded": 2, "down": 3}

    def bucket(dt):
        return int((dt - start).total_seconds() // (CELL_HOURS * 3600))

    polled_cols = set()
    for t in set(ts_cache.values()):
        if start <= t <= end:
            polled_cols.add(bucket(t))

    for r in rows:
        t = ts_cache[r["ts"]]
        if not (start <= t <= end):
            continue
        state = r["state"]
        if state not in idx or not r.get("provider"):
            continue
        c = bucket(t)
        for key in (None, r["provider"]):
            if key is not None and key not in acc:
                continue
            if acc[key][c] is None:
                acc[key][c] = [0, 0, 0, 0]
            acc[key][c][idx[state]] += 1

    cells, medians = {}, {}
    for key, cols in acc.items():
        sh = [None if v is None else cell_shares(*v) for v in cols]
        cells[key] = sh
        obs = sorted(s[0] for s in sh if s is not None)
        medians[key] = obs[len(obs) // 2] if obs else 0.0
    return cells, medians, ncols, polled_cols


def daily_up1d(start, top, rows, ts_cache):
    """series[provider][day_index] -> mean up1d | None."""
    acc = {p: [[] for _ in range(WINDOW_DAYS)] for p in top}
    for r in rows:
        p = r.get("provider")
        if p not in acc or r["state"] == "unknown":
            continue
        d = (ts_cache[r["ts"]].date() - start.date()).days
        if 0 <= d < WINDOW_DAYS and r["up1d"] not in ("", None):
            acc[p][d].append(float(r["up1d"]))
    return {p: [sum(v) / len(v) if v else None for v in days]
            for p, days in acc.items()}


def current_state(latest, provider, baseline):
    n = [0, 0, 0, 0]
    idx = {"up": 0, "idle": 1, "degraded": 2, "down": 3}
    for e in latest["endpoints"]:
        if e.get("provider") == provider and e["state"] in idx:
            n[idx[e["state"]]] += 1
    return classify(cell_shares(*n), baseline)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clip(s: str, n: int = 17) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def day_labels(svg, start, x_at, y, theme, step=3):
    for d in range(0, WINDOW_DAYS, step):
        dt = start + timedelta(days=d)
        svg.append(f'<text x="{x_at(d):.1f}" y="{y}" '
                   f'style="font:11px {MONO};fill:{theme["faint"]}">'
                   f'{dt.strftime("%b %d")}</text>')


def render_strip(theme_name, theme, start, end, top, cells, medians,
                 ncols, polled_cols, polls, latest):
    G, CH, GAP = LABEL_W, 19, 5
    CW = PLOT_W / ncols
    W = CANVAS_W
    rows = [None, *top]
    strip_y = len(rows) * (CH + GAP) + 16
    H = strip_y + 20 + 24
    hid = f"hatch-{theme_name}"

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H}" '
         f'font-family="{MONO}" role="img" '
         f'aria-label="Per-provider availability, last {WINDOW_DAYS} days">',
         f'<defs><pattern id="{hid}" width="6" height="6" '
         f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<line x1="0" y1="0" x2="0" y2="6" stroke="{theme["gap"]}" '
         f'stroke-width="1.5" opacity=".55"/></pattern></defs>']

    color = {"up": theme["up"], "idle": theme["idle"],
             "degraded": theme["deg"], "down": theme["down"]}
    for ri, prov in enumerate(rows):
        y = ri * (CH + GAP)
        label = "all endpoints" if prov is None else clip(prov)
        weight = ";font-weight:700" if prov is None else ""
        s.append(f'<text x="{G-9}" y="{y+CH-5}" text-anchor="end" '
                 f'style="font:12.5px {MONO};fill:{theme["soft"]}{weight}">'
                 f'{esc(label)}</text>')
        med = medians[prov]
        for c, sh in enumerate(cells[prov]):
            st = classify(sh, med) if sh is not None else None
            x = G + c * CW
            if st is None:
                s.append(f'<rect x="{x:.1f}" y="{y}" width="{CW-1.3:.1f}" '
                         f'height="{CH}" rx="2" fill="url(#{hid})" '
                         f'stroke="{theme["rule"]}" stroke-width=".4"/>')
            else:
                s.append(f'<rect x="{x:.1f}" y="{y}" width="{CW-1.3:.1f}" '
                         f'height="{CH}" rx="2" fill="{color[st]}"/>')
        # disclose the row's own norm, so green is never mistaken for "0%"
        s.append(f'<text x="{G+PLOT_W+7:.1f}" y="{y+CH-5}" '
                 f'style="font:11px {MONO};fill:{theme["faint"]}">'
                 f'typ {medians[prov]*100:.0f}%</text>')

    # sampling coverage: one tick per actual poll, at 15-minute resolution
    span_s = (end - start).total_seconds()
    plot_w = PLOT_W
    s.append(f'<text x="{G-9}" y="{strip_y+14}" text-anchor="end" '
             f'style="font:11px {MONO};fill:{theme["faint"]}">polls</text>')
    s.append(f'<rect x="{G}" y="{strip_y}" width="{plot_w:.1f}" height="20" '
             f'fill="none" stroke="{theme["rule"]}" stroke-width="1"/>')
    tick_w = max(plot_w * 900 / span_s, 0.7)   # 15 min of width, floor 0.7px
    for t in polls:
        x = G + (t - start).total_seconds() / span_s * plot_w
        s.append(f'<rect x="{x:.1f}" y="{strip_y+3}" width="{tick_w:.2f}" '
                 f'height="14" fill="{theme["up"]}" opacity=".8"/>')
    # hatch the cell columns where no poll landed at all
    for c in range(ncols):
        if c not in polled_cols:
            s.append(f'<rect x="{G+c*CW:.1f}" y="{strip_y}" width="{CW:.1f}" '
                     f'height="20" fill="url(#{hid})"/>')

    covered = 0.0
    prev_end = None
    for t in polls:
        a = max((t - timedelta(minutes=30) - start).total_seconds(), 0.0)
        b = (t - start).total_seconds()
        if prev_end is not None and a < prev_end:
            a = prev_end
        covered += max(b - a, 0.0)
        prev_end = max(prev_end or 0.0, b)
    duty = 100.0 * covered / span_s if span_s else 0.0
    s.append(f'<text x="{G+plot_w:.1f}" y="{strip_y-4}" text-anchor="end" '
             f'style="font:11.5px {MONO};fill:{theme["faint"]}">'
             f'{len(polls)} polls · 30-min duty {duty:.0f}% · '
             f'{latest["endpoint_count"]} endpoints</text>')

    day_labels(s, start, lambda d: G + d / WINDOW_DAYS * PLOT_W,
               strip_y + 20 + 16, theme)
    s.append("</svg>")
    return "".join(s)


def render_providers(theme, top, series, latest, medians):
    G, RH = LABEL_W, 34
    SX = G + 36                    # sparkline starts just past the state dot
    SW = PLOT_W - 36 - 190         # leaves room for the two numeric columns
    W, header = CANVAS_W, 20
    H = header + len(top) * RH + 8
    color = {"up": theme["up"], "idle": theme["idle"],
             "degraded": theme["deg"], "down": theme["down"]}

    vals = [v for p in top for v in series[p] if v is not None]
    lo = min(min(vals) - 0.5, 97.0) if vals else 90.0
    hi = 100.3

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'font-family="{MONO}" role="img" '
         f'aria-label="Per-provider {WINDOW_DAYS}-day availability from up1d">']
    for x, t in ((G - 8, "provider"), (SX, f"daily up1d, {WINDOW_DAYS} d"),
                 (SX + SW + 34, "mean"), (SX + SW + 118, "worst day")):
        anchor = ' text-anchor="end"' if x == G - 8 else ""
        s.append(f'<text x="{x}" y="10"{anchor} '
                 f'style="font:11px {MONO};fill:{theme["faint"]}">{t}</text>')

    for ri, p in enumerate(top):
        y = header + ri * RH
        cy = y + RH / 2
        st = current_state(latest, p, medians[p])
        s.append(f'<circle cx="{G+13}" cy="{cy:.1f}" r="5" fill="{color[st]}"/>')
        s.append(f'<text x="{G-9}" y="{cy+4.5:.1f}" text-anchor="end" '
                 f'style="font:12.5px {MONO};fill:{theme["soft"]}">'
                 f'{esc(clip(p))}</text>')
        pts, run = [], []
        known = [v for v in series[p] if v is not None]
        for d, v in enumerate(series[p]):
            if v is None:
                if run:
                    pts.append(run)
                run = []
                continue
            px = SX + d * SW / (WINDOW_DAYS - 1)
            py = y + RH - 7 - (v - lo) / (hi - lo) * (RH - 13)
            run.append(f"{px:.1f},{py:.1f}")
        if run:
            pts.append(run)
        for seg in pts:
            if len(seg) == 1:
                x0, y0 = seg[0].split(",")
                s.append(f'<circle cx="{x0}" cy="{y0}" r="2.2" '
                         f'fill="{theme["accent"]}"/>')
            else:
                s.append(f'<polyline points="{" ".join(seg)}" fill="none" '
                         f'stroke="{theme["accent"]}" stroke-width="2" '
                         f'stroke-linejoin="round"/>')
        if known:
            mean, worst = sum(known) / len(known), min(known)
            s.append(f'<text x="{SX+SW+34}" y="{cy+4.5:.1f}" '
                     f'style="font:13px {MONO};fill:{theme["ink"]}">'
                     f'{mean:.2f}%</text>')
            s.append(f'<text x="{SX+SW+96}" y="{cy+3.5:.1f}" '
                     f'style="font:12px {MONO};fill:'
                     f'{theme["down"] if worst < 98 else theme["faint"]}">'
                     f'{worst:.1f}%</text>')
    s.append("</svg>")
    return "".join(s)


def main() -> None:
    latest, start, end, top, rows, ts_cache, polls = load_window()
    cells, medians, ncols, polled_cols = build_cells(start, end, top, rows, ts_cache)
    series = daily_up1d(start, top, rows, ts_cache)

    for name, theme in THEMES.items():
        (STATUS / f"strip-{name}.svg").write_text(
            render_strip(name, theme, start, end, top, cells, medians,
                         ncols, polled_cols, polls, latest))
        (STATUS / f"providers-{name}.svg").write_text(
            render_providers(theme, top, series, latest, medians))
    print(f"charts: {len(polls)} polls, {len(top)} providers, "
          f"{ncols} cells over {WINDOW_DAYS} d → 4 svg")


if __name__ == "__main__":
    main()
