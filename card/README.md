---
license: mit
pretty_name: OpenRouter Uptime
tags:
  - llm
  - infrastructure
  - uptime
  - openrouter
  - time-series
  - mlops
task_categories:
  - time-series-forecasting
configs:
  - config_name: readings
    data_files: readings.parquet
  - config_name: incidents
    data_files: incidents.parquet
  - config_name: models
    data_files: models.parquet
---

# OpenRouter Uptime

An independent, timestamped uptime record for **every model on
[OpenRouter](https://openrouter.ai)** and each of its inference providers.
Polled every 30 minutes from OpenRouter's public API and mirrored here daily.

Source repo (raw + full git history): **https://github.com/dthinkr/openrouter-uptime**

## Files

| file | rows | description |
|---|---|---|
| `readings.parquet` | one per endpoint per poll | `ts, model, provider, state, status, up5m, up30m, up1d` |
| `incidents.parquet` | one per outage edge | endpoint crossing into/out of `down` (`ts, model, provider, from, to, event, up30m`) |
| `models.parquet` | current catalog | `id, name, created, context_length` |
| `providers.parquet` | provider data policies | `slug, name, headquarters, data_policy (training/retention/ToS), moderation_required` |

`state` is one of: `up` (>=98% 30-min uptime), `degraded` (50 to 98%, or
OpenRouter status -2), `down` (<50%, or status -5), `idle` (no recent traffic).

## Why it exists

Built to study operational dependence on AI infrastructure, for example whether
outages of a specific provider move downstream systems. Provider-differential,
model-resolved availability is the raw material. Contributions and research use
welcome.

## Update cadence

Refreshed daily from the live poller. For the 30-minute granular history and the
verbatim raw API archives, use the GitHub repo.
