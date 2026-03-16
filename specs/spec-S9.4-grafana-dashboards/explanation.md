# Spec S9.4: Prometheus + Grafana Dashboards — Explanation

## Why This Spec Exists

CRISIS-BENCH already emits Prometheus metrics from `src/shared/telemetry.py` (S2.5) — LLM requests, tokens, latency, cost, agent tasks, cache operations, and errors. But without alerting rules and dashboards, these metrics sit in Prometheus unseen. S9.4 closes the observability loop: Prometheus alerts when things go wrong, Grafana visualizes everything in real time.

For interviews: this demonstrates production-grade monitoring — not just "we have metrics" but "we have actionable dashboards and automated alerts that page when the $8/month budget is about to be exceeded."

## What It Does

### 1. Prometheus Alerting Rules (`monitoring/alerts.yml`)
Four rules covering the critical failure modes:
- **HighLLMErrorRate**: >10% LLM errors over 5min → warning. Detects provider outages.
- **BudgetExceeded**: cumulative cost > $8 → critical. Prevents runaway spending.
- **AgentTaskTimeout**: p99 agent task duration > 60s → warning. Detects hung agents.
- **CacheHitRateLow**: cache hit rate < 50% → info. Signals plan cache needs tuning.

### 2. Grafana Auto-Provisioning
Grafana starts with everything pre-configured — no manual setup needed:
- **Datasource**: Prometheus at `http://prometheus:9090` auto-registered
- **Dashboard provider**: points to `/var/lib/grafana/dashboards` for JSON files
- **Volume mounts**: Docker Compose mounts provisioning + dashboard directories

### 3. Crisis Ops Dashboard (16 panels, 4 rows)
- **Row 1 — LLM Overview**: Requests/s by provider, tokens/s by direction, cost accumulation per provider
- **Row 2 — Latency**: LLM latency heatmap, p50/p95/p99 percentiles by provider
- **Row 3 — Agents**: Tasks/s by agent, task duration histogram, error rate by error code
- **Row 4 — Cache & Budget**: Cache hit/miss pie chart, budget gauge (green/yellow/red thresholds at 60%/90%), burn rate in USD/hr

## How It Works

All metrics flow through this pipeline:
```
Agent code → telemetry.py (Prometheus counters/histograms)
  → FastAPI /metrics endpoint
  → Prometheus scrapes every 15s
  → Prometheus evaluates alert rules
  → Grafana queries Prometheus
  → Crisis Ops Dashboard renders panels
```

Docker Compose orchestration:
- Prometheus mounts `prometheus.yml` (scrape config) + `alerts.yml` (rules)
- Grafana mounts `provisioning/` (datasources + dashboard providers) + `dashboards/` (JSON files)
- Both on `crisis-net` bridge network for service discovery

## How It Connects

| Component | Relationship |
|-----------|-------------|
| **S2.5 (Telemetry)** | Upstream — defines all Prometheus metrics that this spec visualizes |
| **S1.2 (Docker Compose)** | Modified — added volume mounts for Prometheus alerts and Grafana provisioning |
| **S2.6 (LLM Router)** | Emits `crisis_llm_*` metrics displayed in LLM Overview and Latency rows |
| **S7.1 (Base Agent)** | Emits `crisis_agent_*` metrics displayed in Agents row |
| **S9.1 (Plan Caching)** | Emits `crisis_cache_*` metrics displayed in Cache row |
| **S2.8 (Cost Tracker)** | Future — cost tracker can use the same `crisis_llm_cost_dollars` metric |
| **S9.3 (Langfuse)** | Complementary — Langfuse traces individual LLM calls; Grafana shows aggregate trends |

## Interview Talking Points

**Q: Why Grafana provisioning instead of manual dashboard setup?**
A: Infrastructure-as-code. The dashboard is version-controlled JSON — `docker-compose up` gives you a fully configured Grafana with zero clicks. This is the GitOps principle: the repo IS the source of truth for monitoring, not some manual UI configuration that lives only in Grafana's SQLite database.

**Q: Why these specific alert thresholds?**
A: They map to our system's constraints. $8 budget = monthly cap from roadmap. 10% error rate = more than 1 in 10 LLM calls failing, likely a provider outage. 60s p99 = our circuit breaker timeout, so p99 > 60s means tasks are hitting the breaker. 50% cache hit rate = the plan cache isn't providing value if it misses more than half the time.

**Q: What's the difference between Grafana dashboards and Langfuse?**
A: Different granularity. Grafana shows aggregate operational metrics — "how many requests/second across all agents?" Langfuse shows individual LLM call traces — "what prompt did the orchestrator send, what did it get back, how much did it cost?" Grafana is for ops monitoring (is the system healthy?), Langfuse is for LLM debugging (why did the agent make that decision?).
