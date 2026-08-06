# OpenRouter Uptime

An independent, git-timestamped uptime registry for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.

A GitHub Action polls OpenRouter's public API every hour, saves the raw
responses, records the status of all ~875 model/provider endpoints plus each
provider's metadata, and commits the result. Every poll is a timestamped
snapshot in `raw/` and `derived/`, so any endpoint's availability can be
reconstructed over time from the files themselves.

No API key required. Everything comes from OpenRouter's public endpoints.

**Mirrors:** this repo is the source of truth; a tidy Parquet copy is refreshed
daily on
[HuggingFace](https://huggingface.co/datasets/venvoo/openrouter-uptime) and
[Kaggle](https://www.kaggle.com/datasets/spicycorn/openrouter-uptime).

## What's in here

Three committed folders: `raw/` (verbatim archives), `derived/` (tidy CSVs),
`status/` (current snapshots and change logs).

| path | contents |
|---|---|
| `raw/YYYY-MM-DD/HHMMSS.json.gz` | ground truth: the verbatim `/models`, `/providers` (formerly `/all-providers`), and every `/endpoints` API response for that run. Everything below is derived from these and can be rebuilt with `scripts/reparse.py`. |
| `derived/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, state, status, up5m, up30m, up1d` |
| `status/latest.json` | most recent full endpoint snapshot |
| `status/incidents.jsonl` | append-only outage log; each line is an endpoint crossing into or out of `down` |
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
- GitHub's scheduled runs are best-effort and can lag 5 to 15 min at peak; the
  `ts` column records the true poll time.
- Raw archives are ~140 KB gzipped per run (~7 MB/day).
- OpenRouter's uptime figures are its own measurements of its routing layer.
- Built to study AI-infrastructure dependence; contributions welcome.

<!-- AUTOGEN:STATUS -->

## Current status (2026-08-06T20:00:25+00:00 UTC)

332 models polled, 1060 inference endpoints:
up 696, degraded 113, down 23, idle 228.

Currently down (23):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `amazon/nova-lite-v1` | Amazon Bedrock | 65% | n/a |
| `amazon/nova-micro-v1` | Amazon Bedrock | 29% | 22% |
| `anthropic/claude-fable-5` | Azure | 79% | n/a |
| `deepseek/deepseek-v3.2` | Venice | 79% | 100% |
| `deepseek/deepseek-v4-flash` | Phala | 73% | n/a |
| `deepseek/deepseek-v4-flash-0731` | Together | 80% | 91% |
| `deepseek/deepseek-v4-pro` | Venice | 27% | n/a |
| `google/gemini-2.5-pro` | Google | 60% | n/a |
| `google/gemini-2.5-pro-preview` | Google | 60% | n/a |
| `google/gemini-2.5-pro-preview-05-06` | Google | 59% | n/a |
| `google/gemma-4-31b-it` | SiliconFlow | 8% | n/a |
| `meta-llama/llama-3.3-70b-instruct` | Nebius | 44% | n/a |
| `mistralai/mistral-nemo` | Novita | 68% | 99% |
| `moonshotai/kimi-k2.6` | Fireworks | n/a | n/a |
| `openai/gpt-oss-120b` | DeepInfra | 72% | 100% |
| plus 8 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

<!-- AUTOGEN:EVENTS:BEGIN -->

### Systemic events
_Fleet-level changes extracted from the change logs every run; per-model churn is omitted._

- **2026-07-23 23:58** — provider `wandb` left the platform.
- **2026-07-24 03:19** — provider `wandb-legacy` left the platform.
- **2026-07-27 10:40** — **3 models added to the catalog in one poll**: `inflection/inflection-3-pi`, `inflection/inflection-3-productivity`, `openai/gpt-4o-mini-search-preview`.
- **2026-07-27 13:37** — **3 models removed from the catalog in one poll**: `inflection/inflection-3-pi`, `inflection/inflection-3-productivity`, `openai/gpt-4o-mini-search-preview`.
- **2026-07-28 00:00** — provider `voyageai` changed its terms of service url.
- **2026-07-28 00:00** — provider `voyageai` changed its privacy policy url.
- **2026-07-28 16:39** — **28 models added to the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-haiku-4.5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `anthropic/claude-opus-5:batch`, +20 more.
- **2026-07-30 15:51** — provider `phala` changed its terms of service url.
- **2026-07-30 15:51** — provider `phala` changed its privacy policy url.
- **2026-07-30 19:21** — **3 models removed from the catalog in one poll**: `openai/gpt-5-codex`, `openai/o3-deep-research`, `openai/o4-mini-deep-research`.
- **2026-07-31 16:43** — **28 models removed from the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `anthropic/claude-sonnet-4.5:batch`, `anthropic/claude-sonnet-5:batch`, +20 more.
- **2026-08-06 15:11** — **60 models added to the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-haiku-4.5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `anthropic/claude-opus-5:batch`, +52 more.

Full logs: [`status/model_changes.jsonl`](status/model_changes.jsonl), [`status/provider_changes.jsonl`](status/provider_changes.jsonl).

<!-- AUTOGEN:EVENTS:END -->

