# OpenRouter Uptime

An independent, git-timestamped uptime registry for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.

Two independent collectors poll OpenRouter's public API every 15 minutes --
a Railway cron as the primary and a GitHub Action as the fallback, each
standing down when the other has polled recently. Every run saves the raw
responses, records the status of every routing endpoint (~1,150 across ~400
catalog models) plus provider metadata, and commits the result. Every poll is
a timestamped snapshot in `raw/` and `derived/`, so any endpoint's
availability can be reconstructed over time from the files themselves.
Measured sampling characteristics -- duty cycle, gaps, per-hour density --
are published in [`status/coverage.json`](status/coverage.json).

No API key required. Everything comes from OpenRouter's public endpoints.

**Mirrors:** this repo is the source of truth; a tidy Parquet copy is refreshed
daily on
[HuggingFace](https://huggingface.co/datasets/venvoo/openrouter-uptime) and
[Kaggle](https://www.kaggle.com/datasets/spicycorn/openrouter-uptime).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="status/strip-dark.svg">
  <img alt="Per-provider availability over the last 14 days; the bottom strip marks every actual poll" src="status/strip-light.svg" width="100%">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="status/providers-dark.svg">
  <img alt="Per-provider 14-day availability trend from up1d" src="status/providers-light.svg" width="100%">
</picture>

## What's in here

Three committed folders: `raw/` (verbatim archives), `derived/` (tidy CSVs),
`status/` (current snapshots and change logs).

| path | contents |
|---|---|
| `raw/YYYY-MM-DD/HHMMSS.json.gz` | ground truth: the verbatim `/models`, `/providers` (formerly `/all-providers`), and every `/endpoints` API response for that run. Everything below is derived from these and can be rebuilt with `scripts/reparse.py`. |
| `derived/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, endpoint_tag, endpoint_id, identity_ambiguous, state, status, up5m, up30m, up1d`. Endpoint identity is `(model, endpoint_id)` — provider name alone is not unique, since one provider can serve several endpoints for the same model. `state` is `unknown` when the endpoint fetch itself failed. |
| `status/latest.json` | most recent full endpoint snapshot |
| `status/incidents.jsonl` | append-only outage log; each line is an endpoint transition that touches `down` (note `recovered` can mean down→degraded, not necessarily full health — check `to`). Carries `previous_ts`, `observation_gap` and `minutes_since_last_seen`, so transitions bridged across sampling gaps are marked rather than silent. Rebuilt verbatim from `raw/` by `scripts/rebuild_history.py`; `scripts/audit.py` fails if the two ever differ |
| `status/models.json` | live model catalog, refreshed every run (on catalog-fetch failure the last good snapshot is reused and uptime readings continue) |
| `status/model_changes.jsonl` | append-only log of models added to or removed from OpenRouter, plus catalog fetch outages |
| `status/providers.json` | each provider's metadata (HQ, ToS/privacy/status-page URLs). Until 2026-07-15 it also carried OpenRouter's reported data policy (training, prompt retention, moderation); upstream stopped publishing it, so `data_policy` is null after that date (last-known values remain in `raw/`) |
| `status/provider_changes.jsonl` | append-only log of providers added/removed, data-policy edits (pre-2026-07-15), ToS/privacy/status-page URL edits, and fetch outages (the providers surface is best-effort; uptime readings continue through its failures) |

The README's **Systemic events** section (below) is regenerated every run by
`scripts/readme_events.py`: it surfaces only fleet-level signals from those
logs — batch catalog changes (>=3 models in one poll), provider exits, fetch
outages, and upstream schema breaks — and skips per-model churn.

**State** comes from OpenRouter's 30-minute uptime figure:
`up` (>=98%), `degraded` (50 to 98%), `down` (<50% or non-OK status),
`idle` (no recent traffic, not a fault).

## Why raw is kept

The derived CSV/JSON reflect one interpretation of the API. If that parsing is
ever wrong, or we later want a field we didn't extract, `raw/` holds the
complete original response for every run, so nothing is lost to a parser bug.
`python3 scripts/reparse.py raw/.../HHMMSS.json.gz` regenerates the derived rows
from any archive.

## Use the data

```bash
grep anthropic/claude-sonnet derived/$(date -u +%F).csv   # one model, today
jq 'select(.event=="down")' status/incidents.jsonl        # every outage start
python3 scripts/reparse.py raw/2026-07-04/140117.json.gz  # rebuild from raw
ls raw/                                                   # one folder per day
```

## Notes

- Keyless: `poll.py` uses only OpenRouter's public API.
- Schedulers are best-effort; the `ts` column records the true poll time, and
  `status/coverage.json` records what was actually achieved. Until 2026-08-06
  the collector ran hourly at best (21.6% duty cycle for the 30-minute
  window); judge the early series by the coverage file, not the schedule.
- Raw archives are ~160 KB gzipped per run (~15 MB/day at the 15-min cadence).
- OpenRouter's uptime figures are its own measurements of its routing layer.
- Built to study AI-infrastructure dependence; contributions welcome.

<!-- AUTOGEN:STATUS -->

## Current status (2026-08-30T21:15:33+00:00 UTC)

396 models polled, 1238 inference endpoints:
up 780, degraded 99, down 25, idle 334.

Currently down (25):

| model | endpoint | provider | 30m uptime | 5m uptime |
|---|---|---|---|---|
| `arcee-ai/trinity-large-thinking` | `parasail/fp4` | Parasail | n/a | n/a |
| `deepseek/deepseek-chat-v3.1` | `google-vertex/us-west2` | Google | 0% | n/a |
| `deepseek/deepseek-v4-pro` | `nextbit/fp8` | NextBit | 78% | 100% |
| `deepseek/deepseek-v4-pro-0813` | `deepinfra/fp8` | DeepInfra | 72% | 56% |
| `google/gemini-2.5-flash` | `google-vertex` | Google | 29% | 28% |
| `meta-llama/llama-3.3-70b-instruct` | `nebius/fp8` | Nebius | 44% | n/a |
| `mistralai/mistral-nemo` | `deepinfra/fp8` | DeepInfra | 72% | 56% |
| `mistralai/mistral-nemo` | `novita/fp8` | Novita | 77% | 91% |
| `moonshotai/kimi-k2.6` | `fireworks` | Fireworks | n/a | n/a |
| `moonshotai/kimi-k2.7-code` | `parasail/int4` | Parasail | n/a | n/a |
| `moonshotai/kimi-k3` | `together` | Together | 53% | 100% |
| `openai/gpt-oss-120b` | `siliconflow/fp8` | SiliconFlow | 65% | n/a |
| `openai/gpt-oss-20b` | `google-vertex/us-central1` | Google | 38% | n/a |
| `openai/gpt-oss-20b` | `fireworks` | Fireworks | 0% | 0% |
| `qwen/qwen3-vl-30b-a3b-instruct` | `darkbloom/fp4` | Darkbloom | 80% | 79% |
| plus 10 more | | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

<!-- AUTOGEN:EVENTS:BEGIN -->

### Systemic events
_Fleet-level changes extracted from the change logs every run; per-model churn is omitted._

- **2026-08-07 12:30** — provider `upstage` changed its privacy policy url.
- **2026-08-14 00:30** — provider `modelrun` changed its terms of service url.
- **2026-08-14 00:30** — provider `modelrun` changed its privacy policy url.
- **2026-08-20 19:16** — provider `thinkingmachines` changed its terms of service url.
- **2026-08-20 19:16** — provider `thinkingmachines` changed its privacy policy url.
- **2026-08-24 09:30** — **3 models removed from the catalog in one poll**: `inclusionai/ling-2.6-1t`, `inclusionai/ling-2.6-flash`, `inclusionai/ring-2.6-1t`.
- **2026-08-24 13:15** — **3 models removed from the catalog in one poll**: `nvidia/nemotron-3-nano-30b-a3b:free`, `nvidia/nemotron-nano-12b-v2-vl:free`, `nvidia/nemotron-nano-9b-v2:free`.
- **2026-08-28 02:46** — **35 models removed from the catalog in one poll**: `openai/gpt-3.5-turbo:batch`, `openai/gpt-4-turbo:batch`, `openai/gpt-4.1-mini:batch`, `openai/gpt-4.1-nano:batch`, `openai/gpt-4.1:batch`, `openai/gpt-4o-mini:batch`, `openai/gpt-4o:batch`, `openai/gpt-5-codex:batch`, +27 more.
- **2026-08-28 08:16** — **6 models added to the catalog in one poll**: `mistralai/codestral-2508:batch`, `mistralai/ministral-8b-2512:batch`, `mistralai/mistral-large-2512:batch`, `mistralai/mistral-medium-3-5:batch`, `mistralai/mistral-medium-3.1:batch`, `mistralai/mistral-small-2603:batch`.
- **2026-08-28 15:30** — **10 models added to the catalog in one poll**: `deepseek/deepseek-v4-flash-0731:batch`, `google/gemma-4-31b-it:batch`, `meta/muse-glimmer-30b:batch`, `moonshotai/kimi-k3:batch`, `openai/gpt-oss-120b:batch`, `openai/gpt-oss-20b:batch`, `qwen/qwen3.5-9b:batch`, `qwen/qwen3.8-2.4t-a95b:batch`, +2 more.
- **2026-08-28 15:46** — **9 models removed from the catalog in one poll**: `deepseek/deepseek-v4-flash-0731:batch`, `google/gemma-4-31b-it:batch`, `meta/muse-glimmer-30b:batch`, `moonshotai/kimi-k3:batch`, `openai/gpt-oss-120b:batch`, `openai/gpt-oss-20b:batch`, `qwen/qwen3.5-9b:batch`, `thinkingmachines/inkling-small:batch`, +1 more.
- **2026-08-28 19:31** — **9 models added to the catalog in one poll**: `deepseek/deepseek-v4-flash-0731:batch`, `deepseek/deepseek-v4-pro-0813:batch`, `google/gemma-4-31b-it:batch`, `meta/muse-glimmer-30b:batch`, `moonshotai/kimi-k3:batch`, `openai/gpt-oss-120b:batch`, `openai/gpt-oss-20b:batch`, `qwen/qwen3.5-9b:batch`, +1 more.

Full logs: [`status/model_changes.jsonl`](status/model_changes.jsonl), [`status/provider_changes.jsonl`](status/provider_changes.jsonl).

<!-- AUTOGEN:EVENTS:END -->

