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

## Current status (2026-07-05T07:55:16+00:00 UTC)

324 models polled, 875 inference endpoints:
up 519, degraded 98, down 16, idle 242.

Currently down (16):

| model | provider | 30m uptime | 5m uptime |
|---|---|---|---|
| `amazon/nova-micro-v1` | Amazon Bedrock | 73% | 97% |
| `deepseek/deepseek-v4-pro` | Fireworks | 23% | 27% |
| `google/gemma-4-31b-it` | Together | 78% | 70% |
| `openai/gpt-5.4-nano` | OpenAI | 79% | 82% |
| `openai/gpt-oss-120b` | Mara | 61% | n/a |
| `openai/gpt-oss-20b` | Parasail | 68% | 62% |
| `qwen/qwen3-30b-a3b-instruct-2507` | SiliconFlow | 22% | 4% |
| `z-ai/glm-4.6v` | Novita | 75% | n/a |
| `z-ai/glm-4.6v` | Z.AI | 75% | n/a |
| `z-ai/glm-4.7-flash` | Cloudflare | 27% | 8% |
| `z-ai/glm-4.7-flash` | Novita | 61% | 39% |
| `z-ai/glm-5` | GMICloud | 70% | 97% |
| `z-ai/glm-5` | DigitalOcean | 62% | n/a |
| `z-ai/glm-5` | Phala | 74% | n/a |
| `z-ai/glm-5.2` | DekaLLM | 77% | 90% |
| plus 1 more | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

