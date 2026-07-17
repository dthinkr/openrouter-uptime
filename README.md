# OpenRouter Uptime

An independent, git-timestamped availability registry for the model IDs and
routing endpoints exposed by [OpenRouter's](https://openrouter.ai) public API.

A GitHub Action is scheduled hourly (GitHub scheduling is best-effort), saves
the raw responses, records the status of each model/endpoint tag plus each
provider's metadata, and commits the result. The git history *is* the
dataset: every commit is a timestamped observation, so observed endpoint readings
and provider snapshots can be reconstructed over time. OpenRouter does
not expose an immutable ID for simultaneous duplicate-tag rows; those rows are
retained but marked unsuitable for longitudinal incident inference.

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
| `derived/YYYY-MM-DD.csv` | one row per endpoint per poll: `ts, model, provider, endpoint_tag, endpoint_id, identity_ambiguous, state, status, up5m, up30m, up1d` |
| `status/latest.json` | most recent full endpoint snapshot |
| `status/incidents.jsonl` | observed endpoint transitions into/out of `down`; gap-bridged changes are flagged and interval-censored |
| `status/last_seen.json` | last observed state per endpoint, retained across temporary observation gaps |
| `status/models.json` | live model catalog, refreshed every run (on catalog-fetch failure the last good snapshot is reused and uptime readings continue) |
| `status/model_changes.jsonl` | append-only log of models added to or removed from OpenRouter, plus catalog fetch outages |
| `status/providers.json` | each provider's metadata (HQ, ToS/privacy/status-page URLs). Until 2026-07-15 it also carried OpenRouter's reported data policy (training, prompt retention, moderation); upstream stopped publishing it, so `data_policy` is null after that date (last-known values remain in `raw/`) |
| `status/provider_changes.jsonl` | append-only log of providers added/removed, data-policy edits (pre-2026-07-15), ToS/privacy/status-page URL edits, and fetch outages (the providers surface is best-effort; uptime readings continue through its failures) |
| `status/audit.json` | machine-readable schema, uniqueness, incident-duplication, and observed-cadence checks |

**State** comes from OpenRouter's 30-minute uptime figure:
`up` (>=98%), `degraded` (50 to 98%), `down` (<50% or non-OK status),
`idle` (no recent traffic, not a fault).

## Why raw is kept

The derived CSV/JSON reflect one interpretation of the API. If that parsing is
ever wrong, or we later want a field we didn't extract, `raw/` holds the
complete original response for every run, so nothing is lost to a parser bug.
`python3 scripts/reparse.py raw/.../HHMMSS.json.gz` regenerates the derived rows
from any archive. Endpoint identity is `(model, endpoint_id)`, not merely
`(model, provider)`: one provider may expose several regional or priority tags.
For the normal case, `endpoint_id` is the stable upstream tag. If a model exposes
two simultaneous rows with the same tag, those rows receive descriptor
fingerprints and `identity_ambiguous=true`; they are retained as readings but
excluded from longitudinal incident inference. OpenRouter does not expose an
immutable row ID, so raw responses remain canonical.

## Use the data

```bash
grep anthropic/claude-sonnet derived/$(date -u +%F).csv   # one model, today
jq 'select(.event=="down")' status/incidents.jsonl        # every outage start
python3 scripts/reparse.py raw/2026-07-04/140117.json.gz  # rebuild from raw
python3 scripts/rebuild_history.py                         # rebuild all derived history
python3 scripts/audit.py                                   # fail-closed integrity check
git log -p -- derived/                                    # snapshot history
```

## Notes

- Keyless: `poll.py` uses only OpenRouter's public API.
- GitHub's scheduled runs are best-effort. In the first live week, observed
  gaps were often around two hours and occasionally longer; use `ts` to measure
  actual coverage. Short outages can be missed.
- Poll schema v2 preserves endpoint tags and exact catalog model IDs (including
  `:free` and `:thinking` variants). Earlier raw archives preserve endpoint tags
  but were queried by base-model ID; they cannot retroactively supply variant-
  specific endpoint history. The first schema-v2 raw poll is the coverage boundary.
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

## Current status (2026-07-12T17:18:43+00:00 UTC)

345 models polled, 1027 inference endpoints:
up 615, degraded 144, down 34, idle 234.

Currently down (34):

| model | endpoint | provider | 30m uptime | 5m uptime |
|---|---|---|---|---|
| `deepseek/deepseek-chat-v3-0324` | `deepinfra/fp4` | DeepInfra | 36% | 79% |
| `deepseek/deepseek-chat-v3.1` | `mara` | Mara | 80% | 99% |
| `deepseek/deepseek-v4-flash` | `akashml/fp8` | AkashML | 15% | 0% |
| `google/gemini-2.5-flash` | `google-vertex` | Google | 57% | n/a |
| `google/gemini-2.5-pro` | `google-vertex/eu` | Google | 40% | n/a |
| `google/gemini-2.5-pro-preview` | `google-vertex/eu` | Google | 40% | n/a |
| `google/gemini-2.5-pro-preview-05-06` | `google-vertex/eu` | Google | 41% | n/a |
| `google/gemini-3.1-flash-lite-preview` | `google-vertex/global` | Google | 0% | 0% |
| `google/gemini-3.1-flash-lite-preview` | `google-vertex/global/flex` | Google | 0% | 0% |
| `google/gemini-3.1-flash-lite-preview` | `google-vertex/global/priority` | Google | 0% | 0% |
| `google/gemma-3-27b-it` | `novita/bf16` | Novita | 79% | 88% |
| `google/gemma-3-27b-it` | `phala` | Phala | 65% | 24% |
| `google/gemma-4-26b-a4b-it` | `siliconflow/fp8` | SiliconFlow | 14% | n/a |
| `google/gemma-4-31b-it` | `chutes/fp4` | Chutes | 58% | 29% |
| `google/gemma-4-31b-it` | `siliconflow/fp8` | SiliconFlow | 48% | 95% |
| plus 19 more | | | | |

Full snapshot: [`status/latest.json`](status/latest.json). Outage log: [`status/incidents.jsonl`](status/incidents.jsonl).

