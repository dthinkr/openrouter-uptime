#!/usr/bin/env python3
"""Measure how much of wall-clock time this dataset actually observes.

The collector is scheduled, not continuous, and GitHub's cron drops runs.
Publishing the availability series without publishing its sampling
characteristics invites readers to treat gaps as data. This writes
status/coverage.json so the sampling is a stated property of the dataset
rather than something a reader has to reconstruct.

The headline number is duty cycle. `state` is derived from up30m, a
30-minute trailing window, so a poll at time t speaks for [t-30m, t] and
nothing else. Duty cycle is the union of those windows over the observed
span. Consecutive polls more than 30 minutes apart leave wall-clock that no
observation covers, and those intervals are listed individually -- a reader
resampling the series needs to know where not to interpolate.

up1d is reported separately because its 24-hour window survives the same
sampling almost intact, which makes it the one column that supports
day-scale claims.
"""

from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"
STATUS = ROOT / "status"

# The trailing window behind up30m / up1d, in minutes. A poll speaks for
# exactly this much wall-clock behind itself.
WINDOW_30M = 30.0
WINDOW_1D = 24 * 60.0

# Intervals longer than the 30-minute window open a hole in the up30m series.
# Anything at or below it is contiguous coverage.
GAP_THRESHOLD_MIN = WINDOW_30M


def poll_timestamps() -> list[datetime]:
    """Distinct poll instants, ascending, read from the derived CSVs."""
    seen: set[str] = set()
    for path in sorted(DERIVED.glob("*.csv")):
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                ts = row.get("ts")
                if ts:
                    seen.add(ts)

    out = []
    for raw in seen:
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            continue
        out.append(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
    return sorted(out)


def union_minutes(polls: list[datetime], window_min: float) -> float:
    """Wall-clock minutes covered by at least one [t-window, t] interval."""
    if not polls:
        return 0.0
    covered = 0.0
    cur_start = polls[0] - timedelta(minutes=window_min)
    cur_end = polls[0]
    for t in polls[1:]:
        start = t - timedelta(minutes=window_min)
        if start <= cur_end:
            cur_end = max(cur_end, t)
        else:
            covered += (cur_end - cur_start).total_seconds() / 60.0
            cur_start, cur_end = start, t
    covered += (cur_end - cur_start).total_seconds() / 60.0
    return covered


def main() -> None:
    polls = poll_timestamps()
    if len(polls) < 2:
        raise SystemExit("need at least two polls to describe coverage")

    first, last = polls[0], polls[-1]
    span_min = (last - first).total_seconds() / 60.0

    intervals = [
        (polls[i + 1] - polls[i]).total_seconds() / 60.0 for i in range(len(polls) - 1)
    ]
    ordered = sorted(intervals)

    def pct(p: float) -> float:
        idx = min(len(ordered) - 1, int(round(p / 100.0 * (len(ordered) - 1))))
        return round(ordered[idx], 1)

    gaps = [
        {
            "from": polls[i].isoformat(),
            "to": polls[i + 1].isoformat(),
            "minutes": round(intervals[i], 1),
            "uncovered_minutes": round(intervals[i] - WINDOW_30M, 1),
        }
        for i in range(len(intervals))
        if intervals[i] > GAP_THRESHOLD_MIN
    ]
    gaps.sort(key=lambda g: g["minutes"], reverse=True)

    by_hour = {f"{h:02d}": 0 for h in range(24)}
    for t in polls:
        by_hour[f"{t.astimezone(timezone.utc).hour:02d}"] += 1
    unsampled = [h for h, n in by_hour.items() if n == 0]

    # Only the interior of the span can be covered; the first poll's window
    # reaches back before observation began, so clamp both to the span.
    cov30 = min(union_minutes(polls, WINDOW_30M), span_min + WINDOW_30M) - WINDOW_30M
    cov1d = min(union_minutes(polls, WINDOW_1D), span_min + WINDOW_1D) - WINDOW_1D

    now = datetime.now(timezone.utc)

    report = {
        "generated": now.replace(microsecond=0).isoformat(),
        # How long since anything was collected. The failure this project
        # actually suffered was not a crash but a scheduler that quietly did
        # nothing, which looks identical to "no news" unless something states
        # the age out loud.
        "staleness_hours": round((now - last).total_seconds() / 3600.0, 2),
        "span": {
            "first_poll": first.isoformat(),
            "last_poll": last.isoformat(),
            "hours": round(span_min / 60.0, 1),
        },
        "polls": {
            "count": len(polls),
            "per_day": round(len(polls) / (span_min / 1440.0), 1),
        },
        "interval_minutes": {
            "median": round(statistics.median(intervals), 1),
            "mean": round(statistics.fmean(intervals), 1),
            "p90": pct(90),
            "max": round(max(intervals), 1),
            "over_30_min": sum(1 for v in intervals if v > GAP_THRESHOLD_MIN),
        },
        # The number that matters. 100% means every minute of the span falls
        # inside some poll's 30-minute window; anything less means the series
        # is silent about the remainder.
        "duty_cycle_pct": {
            "up30m": round(100.0 * max(cov30, 0.0) / span_min, 1),
            "up1d": round(100.0 * max(cov1d, 0.0) / span_min, 1),
        },
        "polls_by_utc_hour": by_hour,
        "unsampled_utc_hours": unsampled,
        "gaps": gaps[:50],
        "gap_count": len(gaps),
        "notes": [
            "A poll at time t observes the window [t-30m, t] for up30m and "
            "[t-24h, t] for up1d. Duty cycle is the union of those windows "
            "over the span.",
            "Intervals longer than 30 minutes leave wall-clock unobserved. Do "
            "not interpolate the up30m-derived state column across the "
            "listed gaps.",
            "up1d tolerates this sampling almost intact and is the column "
            "that supports day-scale claims.",
        ],
    }

    STATUS.mkdir(exist_ok=True)
    (STATUS / "coverage.json").write_text(json.dumps(report, indent=1) + "\n")

    d = report["duty_cycle_pct"]
    print(
        f"coverage: {report['polls']['count']} polls over "
        f"{report['span']['hours']}h, median {report['interval_minutes']['median']} min, "
        f"duty cycle up30m={d['up30m']}% up1d={d['up1d']}%, "
        f"{report['gap_count']} gaps, unsampled hours: {unsampled or 'none'}"
    )


if __name__ == "__main__":
    main()
