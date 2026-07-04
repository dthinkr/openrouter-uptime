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

## Current status — 2026-07-04T14:04:07+00:00 UTC

- **324** models polled, **875** inference endpoints
- **120** currently down or degraded
- **0** state changes in the last poll

| model | provider | state | uptime 5m | uptime 30m |
|---|---|---|---|---|
| `anthropic/claude-fable-5` | Google | **down** | 63.6% | 82.9% |
| `anthropic/claude-fable-5` | Anthropic | **down** | 84.0% | 85.0% |
| `deepseek/deepseek-chat-v3-0324` | SiliconFlow | **down** | 95.9% | 94.8% |
| `deepseek/deepseek-chat-v3.1` | SiliconFlow | **down** | 95.7% | 87.3% |
| `deepseek/deepseek-r1` | Azure | **down** | 94.3% | 93.3% |
| `deepseek/deepseek-v4-pro` | Fireworks | **down** | 41.1% | 29.9% |
| `google/gemini-2.5-flash` | Google | **down** | — | 58.4% |
| `google/gemini-2.5-pro` | Google | **down** | 93.2% | 94.5% |
| `google/gemini-2.5-pro-preview-05-06` | Google | **down** | 93.2% | 94.5% |
| `google/gemma-3-27b-it` | Novita | **down** | 88.9% | 84.8% |
| `google/gemma-3-27b-it` | Phala | **down** | 96.9% | 80.1% |
| `google/gemma-4-26b-a4b-it` | Cloudflare | **down** | 52.4% | 68.3% |
| `google/gemma-4-31b-it` | Chutes | **down** | 93.7% | 77.2% |
| `google/gemma-4-31b-it` | Parasail | **down** | 93.9% | 92.1% |
| `google/gemma-4-31b-it` | Phala | **down** | — | 77.5% |
| `google/gemma-4-31b-it` | Together | **down** | 94.5% | 91.5% |
| `meta-llama/llama-3.3-70b-instruct` | DeepInfra | **down** | 93.4% | 94.8% |
| `meta-llama/llama-3.3-70b-instruct` | Google | **down** | 90.3% | 91.9% |
| `minimax/minimax-m2.7` | Mara | **down** | 80.4% | 94.2% |
| `minimax/minimax-m2.7` | Morph | **down** | 100.0% | 94.7% |
| `minimax/minimax-m3` | Parasail | **down** | 87.0% | 92.3% |
| `mistralai/mistral-nemo` | DekaLLM | **down** | 97.4% | 89.5% |
| `mistralai/mistral-nemo` | Novita | **down** | 75.1% | 84.8% |
| `moonshotai/kimi-k2.6` | Together | **down** | 69.6% | 93.7% |
| `moonshotai/kimi-k2.7-code` | Together | **down** | 84.8% | 95.0% |
| `nvidia/nemotron-3-super-120b-a12b` | DekaLLM | **down** | 98.0% | 94.4% |
| `nvidia/nemotron-3-ultra-550b-a55b` | DeepInfra | **down** | 90.0% | 86.6% |
| `openai/gpt-5-nano` | OpenAI | **down** | 90.2% | 92.4% |
| `openai/gpt-5.1` | OpenAI | **down** | 68.6% | 74.6% |
| `openai/gpt-5.4-nano` | OpenAI | **down** | 77.9% | 78.9% |
| `openai/gpt-5.5` | OpenAI | **down** | 93.6% | 93.6% |
| `openai/gpt-oss-120b` | Mara | **down** | 27.9% | 30.3% |
| `openai/gpt-oss-20b` | Parasail | **down** | 100.0% | 75.9% |
| `openai/gpt-oss-20b` | Amazon Bedrock | **down** | 84.5% | 86.7% |
| `openai/gpt-oss-20b` | Fireworks | **down** | — | 31.0% |
| `qwen/qwen3-coder` | Google | **down** | — | 63.8% |
| `qwen/qwen3-coder-30b-a3b-instruct` | SiliconFlow | **down** | 92.5% | 85.6% |
| `qwen/qwen3-coder-next` | Ionstream | **down** | 100.0% | 73.2% |
| `qwen/qwen3-vl-235b-a22b-instruct` | Novita | **down** | 91.5% | 93.6% |
| `qwen/qwen3-vl-235b-a22b-thinking` | Alibaba | **down** | — | 94.2% |
| `qwen/qwen3-vl-30b-a3b-instruct` | Phala | **down** | 99.7% | 92.9% |
| `qwen/qwen3.6-27b` | Morph | **down** | — | 59.3% |
| `qwen/qwen3.6-27b` | SiliconFlow | **down** | 96.7% | 94.8% |
| `qwen/qwen3.6-35b-a3b` | AtlasCloud | **down** | 95.9% | 92.7% |
| `qwen/qwen3.6-35b-a3b` | SiliconFlow | **down** | 70.9% | 79.0% |
| `stepfun/step-3.7-flash` | StepFun | **down** | 92.4% | 91.5% |
| `stepfun/step-3.7-flash` | Novita | **down** | — | 80.5% |
| `undi95/remm-slerp-l2-13b` | NextBit | **down** | — | 94.4% |
| `xiaomi/mimo-v2.5` | Parasail | **down** | 36.8% | 91.2% |
| `xiaomi/mimo-v2.5` | DeepInfra | **down** | 75.4% | 77.3% |
| `xiaomi/mimo-v2.5-pro` | DeepInfra | **down** | 76.7% | 93.5% |
| `z-ai/glm-4.6v` | Novita | **down** | — | 93.4% |
| `z-ai/glm-4.7-flash` | Cloudflare | **down** | 17.5% | 16.5% |
| `z-ai/glm-4.7-flash` | Novita | **down** | 67.9% | 70.6% |
| `z-ai/glm-5` | Z.AI | **down** | 94.4% | 94.4% |
| `z-ai/glm-5` | Parasail | **down** | 96.7% | 94.0% |
| `z-ai/glm-5-turbo` | Z.AI | **down** | — | 90.1% |
| `z-ai/glm-5.1` | DigitalOcean | **down** | — | 69.2% |
| `z-ai/glm-5.1` | AtlasCloud | **down** | 92.1% | 93.2% |
| `z-ai/glm-5.1` | Novita | **down** | 96.7% | 92.0% |
| … | +60 more | | | |

