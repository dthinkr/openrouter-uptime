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

## Current status (2026-08-05T05:44:04+00:00 UTC)

329 models polled, 1057 inference endpoints:
up 655, degraded 136, down 21, idle 245.

Currently down (21):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `amazon/nova-micro-v1` | Amazon Bedrock | 6% | 6% |
| `amazon/nova-micro-v1` | Amazon Bedrock | 63% | 100% |
| `anthropic/claude-fable-5` | Anthropic | 38% | n/a |
| `deepseek/deepseek-r1` | Azure | n/a | n/a |
| `deepseek/deepseek-v3.2` | Venice | 54% | n/a |
| `deepseek/deepseek-v4-flash-0731` | Together | 79% | 77% |
| `deepseek/deepseek-v4-flash-0731` | Mancer 2 | 64% | n/a |
| `deepseek/deepseek-v4-pro` | Venice | 27% | n/a |
| `google/gemini-2.5-flash` | Google | 51% | 51% |
| `meta-llama/llama-3.3-70b-instruct` | Nebius | 63% | n/a |
| `minimax/minimax-m2.5` | Phala | n/a | n/a |
| `mistralai/mistral-nemo` | Novita | 61% | 58% |
| `moonshotai/kimi-k2-thinking` | Google | 77% | n/a |
| `moonshotai/kimi-k2.6` | SiliconFlow | 78% | n/a |
| `openai/gpt-5.6-sol` | OpenAI | 78% | 37% |
| plus 6 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

<!-- AUTOGEN:EVENTS:BEGIN -->

### Systemic events
_Fleet-level changes extracted from the change logs every run; per-model churn is omitted._

- **2026-07-23 02:32** — **25 models removed from the catalog in one poll**: `anthropic/claude-fable-5:batch`, `anthropic/claude-opus-4.1:batch`, `anthropic/claude-opus-4.5:batch`, `anthropic/claude-opus-4.6:batch`, `anthropic/claude-opus-4.7:batch`, `anthropic/claude-opus-4.8:batch`, `openai/gpt-3.5-turbo:batch`, `openai/gpt-4-turbo:batch`, +17 more.
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

Full logs: [`status/model_changes.jsonl`](status/model_changes.jsonl), [`status/provider_changes.jsonl`](status/provider_changes.jsonl).

<!-- AUTOGEN:EVENTS:END -->

