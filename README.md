# OpenRouter Uptime

An independent, git-timestamped uptime registry for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.

A GitHub Action polls OpenRouter's public API every hour, saves the raw
responses, records the status of all ~875 model/provider endpoints plus each
provider's data policy, and commits the result. The git history *is* the
dataset: every commit is a timestamped snapshot, so any endpoint's availability
or any provider's policy can be reconstructed over time.

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
| `raw/YYYY-MM-DD/HHMMSS.json.gz` | ground truth: the verbatim `/models`, `/all-providers`, and every `/endpoints` API response for that run. Everything below is derived from these and can be rebuilt with `scripts/reparse.py`. |
| `derived/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, state, status, up5m, up30m, up1d` |
| `status/latest.json` | most recent full endpoint snapshot |
| `status/incidents.jsonl` | append-only outage log; each line is an endpoint crossing into or out of `down` |
| `status/models.json` | live model catalog, refreshed every run |
| `status/model_changes.jsonl` | append-only log of models added to or removed from OpenRouter |
| `status/providers.json` | each provider's data policy (training, prompt retention, ToS/privacy URLs, moderation) |
| `status/provider_changes.jsonl` | append-only log of providers added/removed and data-policy edits |

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
git log -p -- derived/                                    # snapshot history
```

## Notes

- Keyless: `poll.py` uses only OpenRouter's public API.
- GitHub's scheduled runs are best-effort and can lag 5 to 15 min at peak; the
  `ts` column records the true poll time.
- Raw archives are ~140 KB gzipped per run (~7 MB/day).
- OpenRouter's uptime figures are its own measurements of its routing layer.
- Built to study AI-infrastructure dependence; contributions welcome.

## Citation

Use the "Cite this repository" button on GitHub, or:

```bibtex
@misc{wu_openrouter_uptime_2026,
  author       = {Wu, Wenbin},
  title        = {OpenRouter Uptime: an independent availability and
                  data-policy registry for OpenRouter models},
  year         = {2026},
  howpublished = {\url{https://github.com/dthinkr/openrouter-uptime}}
}
```

<!-- AUTOGEN:STATUS -->

## Current status (2026-07-11T02:27:45+00:00 UTC)

329 models polled, 1006 inference endpoints:
up 591, degraded 125, down 43, idle 247.

Currently down (43):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `amazon/nova-micro-v1` | Amazon Bedrock | 78% | 94% |
| `deepseek/deepseek-chat-v3-0324` | DeepInfra | 64% | n/a |
| `deepseek/deepseek-v4-flash` | WandB | 0% | 0% |
| `deepseek/deepseek-v4-pro` | Alibaba | 49% | n/a |
| `deepseek/deepseek-v4-pro` | WandB | 0% | 0% |
| `google/gemini-2.5-flash` | Google | 47% | n/a |
| `google/gemini-3.1-flash-lite-preview` | Google | 0% | 0% |
| `google/gemini-3.1-flash-lite-preview` | Google | 0% | 0% |
| `google/gemini-3.1-flash-lite-preview` | Google | 0% | 0% |
| `google/gemma-3-27b-it` | Phala | 23% | 37% |
| `google/gemma-4-26b-a4b-it` | Cloudflare | 66% | 78% |
| `google/gemma-4-26b-a4b-it` | SiliconFlow | 11% | n/a |
| `google/gemma-4-31b-it` | Chutes | 32% | 23% |
| `google/gemma-4-31b-it` | SiliconFlow | 0% | 0% |
| `google/gemma-4-31b-it` | Novita | 70% | 96% |
| plus 28 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

