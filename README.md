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

## Current status (2026-07-23T22:53:42+00:00 UTC)

333 models polled, 1053 inference endpoints:
up 676, degraded 112, down 28, idle 237.

Currently down (28):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `deepseek/deepseek-v3.2` | Alibaba | n/a | n/a |
| `deepseek/deepseek-v4-pro` | Together | 77% | 98% |
| `google/gemini-3-pro-image-preview` | Google | 0% | n/a |
| `google/gemini-3-pro-image-preview` | Google | 0% | n/a |
| `google/gemma-3-27b-it` | Phala | 21% | n/a |
| `google/gemma-4-31b-it` | Phala | 34% | n/a |
| `meta-llama/llama-3.3-70b-instruct` | Nebius | 58% | 63% |
| `meta-llama/llama-3.3-70b-instruct` | Novita | 57% | n/a |
| `mistralai/mistral-nemo` | Novita | 72% | 76% |
| `moonshotai/kimi-k2.5` | Chutes | 70% | n/a |
| `nvidia/nemotron-3-nano-30b-a3b` | Novita | 0% | n/a |
| `openai/gpt-5.1-codex-mini` | OpenAI | n/a | n/a |
| `openai/gpt-5.2-codex` | OpenAI | 0% | n/a |
| `openai/gpt-5.2-codex` | OpenAI | 0% | n/a |
| `openai/gpt-5.4-mini` | OpenAI | 26% | 32% |
| plus 13 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

<!-- AUTOGEN:EVENTS:BEGIN -->

### Systemic events
_Fleet-level changes extracted from the change logs every run; per-model churn is omitted._

- **2026-07-10 16:54** — provider `clarifai` left the platform.
- **2026-07-13 16:30** — provider `liquid` left the platform.
- **2026-07-14 14:47** — provider `infermatic` left the platform.
- **2026-07-17 17:25** — **schema break**: upstream retired /api/frontend/all-providers; data_policy/moderation_required no longer published.
- **2026-07-19 13:17** — **6 models removed from the catalog in one poll**: `cognitivecomputations/dolphin-mistral-24b-venice-edition:free`, `meta-llama/llama-3.2-3b-instruct:free`, `meta-llama/llama-3.3-70b-instruct:free`, `nousresearch/hermes-3-llama-3.1-405b:free`, `qwen/qwen3-coder:free`, `qwen/qwen3-next-80b-a3b-instruct:free`.
- **2026-07-20 17:59** — provider `tencent` changed its terms of service url.
- **2026-07-20 17:59** — provider `tencent` changed its privacy policy url.
- **2026-07-21 17:15** — **4 models added to the catalog in one poll**: `google/gemini-3.5-flash-lite`, `google/gemini-3.6-flash`, `poolside/laguna-s-2.1`, `poolside/laguna-s-2.1:free`.
- **2026-07-22 23:00** — **24 models added to the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `openai/gpt-3.5-turbo:batch`, `openai/gpt-4-turbo:batch`, +16 more.
- **2026-07-22 23:00** — provider `coreweave` changed its terms of service url.
- **2026-07-22 23:00** — provider `coreweave` changed its privacy policy url.
- **2026-07-23 02:32** — **25 models removed from the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `openai/gpt-3.5-turbo:batch`, `openai/gpt-4-turbo:batch`, +17 more.

Full logs: [`status/model_changes.jsonl`](status/model_changes.jsonl), [`status/provider_changes.jsonl`](status/provider_changes.jsonl).

<!-- AUTOGEN:EVENTS:END -->

