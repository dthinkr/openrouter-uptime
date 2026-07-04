# OpenRouter Uptime

An independent, git-timestamped uptime registry for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.

A GitHub Action polls OpenRouter's public API every 30 minutes, saves the raw
responses, records the status of all ~875 model/provider endpoints, and commits
the result. The git history *is* the dataset: every commit is a timestamped
snapshot, so any endpoint's availability can be reconstructed over time.

No API key required. Everything comes from OpenRouter's public endpoints.

## What's in here

| path | contents |
|---|---|
| `raw/YYYY-MM-DD/HHMMSS.json.gz` | ground truth: the verbatim `/models` plus every `/endpoints` API response for that run. Everything below is derived from these and can be rebuilt with `scripts/reparse.py`. |
| `data/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, state, status, up5m, up30m, up1d` |
| `status/latest.json` | most recent full snapshot |
| `status/incidents.jsonl` | append-only outage log; each line is an endpoint crossing into or out of `down` |
| `status/models.json` | the full live model catalog, refreshed every run |
| `status/model_changes.jsonl` | append-only log of models added to or removed from OpenRouter |

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
grep anthropic/claude-sonnet data/$(date -u +%F).csv     # one model, today
jq 'select(.event=="down")' status/incidents.jsonl        # every outage start
python3 scripts/reparse.py raw/2026-07-04/140117.json.gz  # rebuild from raw
git log -p -- data/                                       # snapshot history
```

## Run it yourself

Fork, enable Actions, and the schedule starts automatically with no secrets. Or
once, locally:

```bash
python3 scripts/poll.py && python3 scripts/summarize.py
```

## Notes

- Keyless: `poll.py` uses only OpenRouter's public API.
- GitHub's scheduled runs are best-effort and can lag 5 to 15 min at peak; the
  `ts` column records the true poll time.
- Raw archives are ~140 KB gzipped per run (~7 MB/day).
- OpenRouter's uptime figures are its own measurements of its routing layer.
- Built to study AI-infrastructure dependence; contributions welcome.

<!-- AUTOGEN:STATUS -->

## Current status (2026-07-04T14:41:57+00:00 UTC)

324 models polled, 875 inference endpoints:
up 524, degraded 108, down 27, idle 216.

Currently down (27):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `amazon/nova-micro-v1` | Amazon Bedrock | 61% | n/a |
| `anthropic/claude-fable-5` | Google | 78% | n/a |
| `deepseek/deepseek-chat-v3.1` | SiliconFlow | 66% | 91% |
| `deepseek/deepseek-chat-v3.1` | AtlasCloud | 73% | 100% |
| `deepseek/deepseek-chat-v3.1` | WandB | 77% | 100% |
| `deepseek/deepseek-v4-pro` | Fireworks | 27% | 29% |
| `google/gemini-2.5-flash` | Google | 69% | 93% |
| `google/gemma-4-26b-a4b-it` | Cloudflare | 66% | 56% |
| `google/gemma-4-31b-it` | Chutes | 46% | 59% |
| `google/gemma-4-31b-it` | SiliconFlow | 52% | 98% |
| `google/gemma-4-31b-it` | Phala | 79% | 71% |
| `mistralai/mistral-nemo` | Novita | 71% | 68% |
| `nvidia/nemotron-3-nano-30b-a3b` | Novita | 69% | n/a |
| `nvidia/nemotron-3-ultra-550b-a55b` | DeepInfra | 73% | 88% |
| `nvidia/nemotron-3-ultra-550b-a55b` | Nebius | 62% | n/a |
| plus 12 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

