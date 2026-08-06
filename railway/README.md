# Railway collector

A second collector, running every 15 minutes, alongside the GitHub Actions
schedule.

## Why it exists

GitHub's cron is best-effort by design: it drops scheduled runs rather than
merely delaying them. Under `cron: "0 * * * *"` this project delivered **43% of
its nominal hourly rate** across 33 days, the 01:00 UTC hour was never sampled
at all, and the four largest gaps after the July outage all fell between 00:00
and 06:00 UTC. The dropouts are diurnal, not random, so no amount of tuning on
that platform reaches continuous coverage.

## Why 15 minutes

The cadence is set by the measurement, not by preference.

`state` derives from `up30m`, a 30-minute trailing window, so a poll at time
*t* speaks for `[t-30m, t]` and nothing else. Consecutive polls more than 30
minutes apart leave wall-clock that no observation covers.

At 15 minutes the windows overlap by half, which means **a single missed run
still leaves no hole**:

```
t      poll  → covers [t-30, t]
t+15   missed
t+30   poll  → covers [t,   t+30]
                       union = [t-30, t+30], contiguous
```

That single-fault tolerance is what removes the need for a third collector.
Only two consecutive misses open a gap.

Missed observations cannot be backfilled — OpenRouter reports only current
windows and offers no historical endpoint — so every design choice here favours
taking an extra sample over risking a skipped one.

## How the two collectors coexist

They do not coordinate. Both run `scripts/should_poll.py` first, which reads
`status/latest.json` and stands down if the last poll is inside the freshness
floor (`MIN_INTERVAL_MIN`, default 12). Whichever arrives first writes; the
other exits without polling. The Actions schedule is left in place as the
fallback for Railway outages.

## Setup

The service needs three things the repository cannot carry: a token, a volume,
and a schedule.

**1. Token.** Create a *fine-grained* personal access token scoped to this
repository alone, with `Contents: Read and write`. Do not reuse a
broadly-scoped classic token — this one lives on a third-party host.

**2. Service.** Point a new Railway service at this repo. `railway.json` selects
`railway/Dockerfile`, sets `restartPolicyType: NEVER` (without which Railway
restarts the container the moment it exits, turning a cron job into a hot
loop), and pins a single replica.

**3. Variables.**

| Variable | Value |
| --- | --- |
| `GITHUB_TOKEN` | the fine-grained PAT from step 1 |
| `REPO_URL` | `https://github.com/dthinkr/openrouter-uptime.git` |
| `BRANCH` | `main` |
| `WORKDIR` | `/data/repo` |
| `MIN_INTERVAL_MIN` | `12` |

**4. Volume.** Mount one at `/data`. Without it the container re-clones the
full repository every quarter hour; with it, the first run clones and every
run after that pulls incrementally.

**5. Schedule.** Set `*/15 * * * *` in the service's own settings, **not** in
`railway.json`. Railway has a known open bug with cron schedules defined
through config-as-code. Railway's minimum granularity is 5 minutes and all
schedules are evaluated in UTC.

**6. Watch patterns.** Restrict rebuilds to:

```
railway/**
scripts/**
railway.json
```

This one is not optional. A Railway service connected to a GitHub repo
rebuilds on every push to the tracked branch by default — and this collector
pushes to that branch every fifteen minutes. Left at the default, each poll
triggers a fresh Docker build, and the build costs considerably more than the
4.5-second poll it exists to run. The service would spend its life rebuilding
itself in response to its own commits.

With the patterns above, `raw/`, `derived/`, `status/` and `README.md` no
longer trigger anything. Only an actual change to the collector rebuilds it.

## Verifying it works

`status/coverage.json` is regenerated daily by the `publish-dataset` workflow
and is the only thing that actually answers the question. Watch three fields:

- `duty_cycle_pct.up30m` — the share of wall-clock covered by some poll's
  30-minute window. It was **21.4%** before this collector existed.
- `interval_minutes.over_30_min` — intervals that opened a hole. Should trend
  toward zero.
- `unsampled_utc_hours` — was `["01"]`. Should be empty.

Do not judge the change by whether runs appear in the Railway log. The failure
mode being fixed is a scheduler that silently does nothing, and a log of
successful runs looks identical whether or not the ones in between fired.

## Cost

The poll itself takes about 4.5 seconds. At 2,920 runs a month with 0.25 vCPU
and 256 MB that is roughly **$0.10–0.30/month** in usage, against the $5 credit
included with Hobby.

The figure only holds if the container actually exits between runs. If Railway
keeps it resident, the same allocation costs about $7.50/month — more than the
whole credit, for a job that runs 4.5 seconds at a time. Check the first
week's usage before assuming which regime applies.
