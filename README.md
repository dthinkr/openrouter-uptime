# OpenRouter Uptime

An independent, git-timestamped uptime registry for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.

A GitHub Action polls OpenRouter's public API every 30 minutes, saves the raw
responses, records the status of all ~875 model×provider endpoints, and commits
the result. The git history *is* the dataset: every commit is a timestamped
snapshot, so any endpoint's availability can be reconstructed over time.

No API key required — everything comes from OpenRouter's public endpoints.

## What's in here

| path | contents |
|---|---|
| `raw/YYYY-MM-DD/HHMMSS.json.gz` | **ground truth** — the verbatim `/models` + every `/endpoints` API response for that run. Everything below is derived from these and can be rebuilt with `scripts/reparse.py`. |
| `data/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, state, status, up5m, up30m, up1d` |
| `status/latest.json` | most recent full snapshot |
| `status/incidents.jsonl` | append-only outage log: each line is an endpoint crossing into or out of `down` |
| `status/models.json` | the full live model catalog, refreshed every run |
| `status/model_changes.jsonl` | append-only log of models added to / removed from OpenRouter |

**State** is derived from OpenRouter's 30-minute uptime figure:
`up` (≥98%) · `degraded` (50–98%) · `down` (<50% or non-OK status) ·
`idle` (no recent traffic — not a fault).

## Why raw is kept

The derived CSV/JSON reflect one interpretation of the API. If that parsing is
ever wrong, or we later want a field we didn't extract, `raw/` holds the
complete original response for every run — nothing is lost to a parser bug.
`python3 scripts/reparse.py raw/…/HHMMSS.json.gz` regenerates the derived rows
from any archive.

## Use the data

```bash
grep anthropic/claude-sonnet data/$(date -u +%F).csv     # one model, today
jq 'select(.event=="down")' status/incidents.jsonl        # every outage start
python3 scripts/reparse.py raw/2026-07-04/140117.json.gz  # rebuild from raw
git log -p -- data/                                       # snapshot history
```

## Run it yourself

Fork, enable Actions — the schedule starts automatically, no secrets. Or once,
locally:

```bash
python3 scripts/poll.py && python3 scripts/summarize.py
```

## Notes

- Keyless: `poll.py` uses only OpenRouter's public API.
- GitHub's scheduled runs are best-effort and can lag 5–15 min at peak; the `ts`
  column records the true poll time.
- Raw archives are ~140 KB gzipped per run (~7 MB/day).
- OpenRouter's uptime figures are its own measurements of its routing layer.
- Built to study AI-infrastructure dependence; contributions welcome.

<!-- AUTOGEN:STATUS -->

## Current status — 2026-07-04T14:06:11+00:00 UTC

- **324** models polled, **875** inference endpoints
- **126** currently down or degraded
- **43** state changes in the last poll

| model | provider | state | uptime 5m | uptime 30m |
|---|---|---|---|---|
| `deepseek/deepseek-v4-pro` | Fireworks | **down** | 47.9% | 32.3% |
| `google/gemini-2.5-flash` | Google | **down** | — | 58.4% |
| `google/gemma-4-26b-a4b-it` | Cloudflare | **down** | 84.2% | 68.4% |
| `google/gemma-4-31b-it` | Phala | **down** | — | 78.0% |
| `nvidia/nemotron-3-ultra-550b-a55b` | DeepInfra | **down** | 41.2% | 61.2% |
| `nvidia/nemotron-3-ultra-550b-a55b` | Nebius | **down** | 72.4% | 75.3% |
| `openai/gpt-5.1` | OpenAI | **down** | 68.6% | 74.6% |
| `openai/gpt-5.4-nano` | OpenAI | **down** | 77.9% | 78.9% |
| `openai/gpt-oss-120b` | Mara | **down** | 27.9% | 30.3% |
| `openai/gpt-oss-20b` | Parasail | **down** | 100.0% | 75.9% |
| `openai/gpt-oss-20b` | Fireworks | **down** | — | 31.0% |
| `qwen/qwen3-coder` | Google | **down** | — | 63.8% |
| `qwen/qwen3-coder-next` | Ionstream | **down** | 100.0% | 73.2% |
| `qwen/qwen3.6-27b` | Morph | **down** | — | 56.4% |
| `qwen/qwen3.6-35b-a3b` | SiliconFlow | **down** | 94.7% | 76.4% |
| `z-ai/glm-4.7-flash` | Cloudflare | **down** | 12.3% | 21.9% |
| `z-ai/glm-4.7-flash` | Novita | **down** | 60.0% | 68.1% |
| `z-ai/glm-5.1` | DigitalOcean | **down** | — | 78.2% |
| `z-ai/glm-5.2` | Cloudflare | **down** | — | 75.0% |
| `anthropic/claude-fable-5` | Google | **degraded** | 63.6% | 82.9% |
| `anthropic/claude-fable-5` | Anthropic | **degraded** | 84.0% | 85.0% |
| `cohere/command-r-08-2024` | Cohere | **degraded** | — | 97.3% |
| `deepseek/deepseek-chat-v3-0324` | SiliconFlow | **degraded** | 95.9% | 94.8% |
| `deepseek/deepseek-chat-v3.1` | SiliconFlow | **degraded** | 95.7% | 87.3% |
| `deepseek/deepseek-r1` | Azure | **degraded** | — | 95.5% |
| `deepseek/deepseek-v3.1-terminus` | SiliconFlow | **degraded** | 96.7% | 97.2% |
| `deepseek/deepseek-v4-flash` | Fireworks | **degraded** | 97.1% | 97.9% |
| `deepseek/deepseek-v4-pro` | StreamLake | **degraded** | 99.8% | 97.4% |
| `deepseek/deepseek-v4-pro` | WandB | **degraded** | 97.9% | 97.7% |
| `deepseek/deepseek-v4-pro` | Together | **degraded** | 98.4% | 97.1% |
| `google/gemini-2.5-pro` | Google | **degraded** | 93.2% | 94.5% |
| `google/gemini-2.5-pro` | Google AI Studio | **degraded** | 97.3% | 96.8% |
| `google/gemini-2.5-pro-preview` | Google | **degraded** | 97.4% | 97.9% |
| `google/gemini-2.5-pro-preview` | Google | **degraded** | 94.7% | 95.6% |
| `google/gemini-2.5-pro-preview` | Google AI Studio | **degraded** | — | 96.9% |
| `google/gemini-2.5-pro-preview-05-06` | Google | **degraded** | 96.8% | 98.0% |
| `google/gemini-2.5-pro-preview-05-06` | Google AI Studio | **degraded** | 100.0% | 96.6% |
| `google/gemini-3.1-flash-image` | Google AI Studio | **degraded** | 95.9% | 96.0% |
| `google/gemini-3.1-flash-image-preview` | Google AI Studio | **degraded** | 97.3% | 97.7% |
| `google/gemini-3.1-flash-lite` | Google | **degraded** | 95.9% | 96.8% |
| `google/gemini-3.1-flash-lite-preview` | Google AI Studio | **degraded** | 97.8% | 97.4% |
| `google/gemma-3-27b-it` | Novita | **degraded** | 88.9% | 84.8% |
| `google/gemma-3-27b-it` | Phala | **degraded** | 96.9% | 80.1% |
| `google/gemma-4-26b-a4b-it` | DekaLLM | **degraded** | 93.8% | 97.7% |
| `google/gemma-4-26b-a4b-it` | SiliconFlow | **degraded** | 90.6% | 95.8% |
| `google/gemma-4-26b-a4b-it` | Venice | **degraded** | 99.4% | 97.5% |
| `google/gemma-4-31b-it` | DeepInfra | **degraded** | 93.0% | 97.0% |
| `google/gemma-4-31b-it` | Chutes | **degraded** | 100.0% | 82.7% |
| `google/gemma-4-31b-it` | SiliconFlow | **degraded** | 86.9% | 91.2% |
| `google/gemma-4-31b-it` | Parasail | **degraded** | 93.3% | 92.4% |
| `google/gemma-4-31b-it` | Together | **degraded** | 98.2% | 92.1% |
| `google/gemma-4-31b-it` | Together | **degraded** | 99.8% | 97.5% |
| `meta-llama/llama-3.3-70b-instruct` | DeepInfra | **degraded** | 93.4% | 94.8% |
| `meta-llama/llama-3.3-70b-instruct` | Nebius | **degraded** | 98.6% | 95.1% |
| `meta-llama/llama-3.3-70b-instruct` | Cloudflare | **degraded** | 98.5% | 97.5% |
| `meta-llama/llama-3.3-70b-instruct` | Google | **degraded** | 90.3% | 91.9% |
| `meta-llama/llama-3.3-70b-instruct` | Together | **degraded** | — | 97.7% |
| `minimax/minimax-m2.5` | Mara | **degraded** | 82.9% | 95.9% |
| `minimax/minimax-m2.7` | Mara | **degraded** | 80.4% | 94.2% |
| `minimax/minimax-m2.7` | Morph | **degraded** | 100.0% | 94.7% |
| … | +66 more | | | |

