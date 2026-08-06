#!/usr/bin/env python3
"""Decide whether a poll is due.

The collector is deliberately over-scheduled. GitHub's cron drops runs rather
than merely delaying them -- that is why coverage sat at 43% of the nominal
hourly rate -- so the workflow fires several times an hour and relies on this
guard to turn the surplus attempts into no-ops. The same guard lets a second
collector (Railway) run on a tighter cadence without the two of them
double-polling: whoever arrives first writes, the other sees a fresh timestamp
and stands down.

Freshness is read from status/latest.json, which poll.py rewrites on every
successful run. A missing or unparseable file means "poll" -- on a cold start
we would rather take an extra sample than none.

Exit code is always 0. The decision is communicated on stdout and, under
GitHub Actions, through the `poll` step output.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATEST = ROOT / "status" / "latest.json"

# Minimum spacing between polls. Kept a little under half the 15-minute target
# cadence so a late-but-not-dropped run still counts rather than being
# suppressed by the run before it.
DEFAULT_MIN_INTERVAL_MIN = 12.0


def last_poll_utc() -> datetime | None:
    """Timestamp of the most recent successful poll, or None if unknown."""
    try:
        generated = json.loads(LATEST.read_text())["generated"]
    except (OSError, ValueError, KeyError):
        return None
    try:
        ts = datetime.fromisoformat(generated)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def emit(should_poll: bool, reason: str, age_min: float | None) -> None:
    age = "unknown" if age_min is None else f"{age_min:.1f} min"
    print(f"poll={'true' if should_poll else 'false'}  last={age}  {reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"poll={'true' if should_poll else 'false'}\n")
            fh.write(f"age_minutes={'' if age_min is None else round(age_min, 1)}\n")


def main() -> None:
    if os.environ.get("FORCE_POLL", "").lower() in ("1", "true", "yes"):
        emit(True, "forced", None)
        return

    try:
        min_interval = float(
            os.environ.get("MIN_INTERVAL_MIN") or DEFAULT_MIN_INTERVAL_MIN
        )
    except ValueError:
        min_interval = DEFAULT_MIN_INTERVAL_MIN

    last = last_poll_utc()
    if last is None:
        emit(True, "no readable previous poll", None)
        return

    age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60.0

    if age_min < 0:
        # Clock skew, or someone hand-edited the file. Polling again is the
        # safe reading: a spurious extra sample costs nothing, a suppressed
        # one is unrecoverable.
        emit(True, "previous poll is in the future; ignoring", age_min)
        return

    if age_min < min_interval:
        emit(False, f"under the {min_interval:g} min floor", age_min)
        return

    emit(True, f"due (floor {min_interval:g} min)", age_min)


if __name__ == "__main__":
    sys.exit(main())
