# S9.3 Langfuse Full Integration — Explanation

## Why This Spec Exists

The S2.5 telemetry module provided a basic `LangfuseTracer` that created flat, disconnected traces — one per LLM call in the router. This made it impossible to see the full picture of an agent task execution: which LLM calls belonged to which agent, how calls were nested within graph nodes, or how much each agent contributed to total cost. S9.3 upgrades the tracer to support hierarchical tracing, prompt versioning, session grouping, and cost attribution — turning Langfuse from a "we have tracing" checkbox into a genuinely useful observability tool.

## What It Does

### Enhanced LangfuseTracer API

The `LangfuseTracer` class in `src/shared/telemetry.py` now supports:

1. **Hierarchical tracing**: `start_trace()` → `start_span()` → `log_generation()`. Agent task execution creates a trace, graph node execution creates spans, LLM calls create generations nested under the correct parent.

2. **Session grouping**: Traces accept a `session_id` parameter, allowing all traces within a benchmark scenario run to be grouped and viewed together in the Langfuse UI.

3. **Prompt versioning**: `register_prompt()` and `get_prompt()` enable tracking system prompt changes per agent type. When a system prompt is modified, a new version is created automatically.

4. **Cost attribution**: Every generation includes metadata with `cost_usd`, `latency_s`, `tier`, and `provider`, enabling per-agent cost analysis in Langfuse.

5. **Graceful degradation**: Every method wraps Langfuse calls in try/except, returning None on failure. No tracing exception can ever crash business logic.

### BaseAgent Integration

`BaseAgent.handle_task()` now:
- Creates a Langfuse trace at the start of task execution
- Ends the trace with `status="ok"` on success or `status="error"` on failure
- The tracer is injected via `self._tracer` (optional, defaults to None)

### LLM Router Integration

`LLMRouter.call()` now accepts an optional `parent_handle` parameter:
- When provided, the router logs the LLM generation under that parent handle
- When not provided, no Langfuse logging occurs (the caller is responsible)
- This enables the BaseAgent to pass its trace handle to the router for nested tracing

## How It Connects

| Component | Connection |
|-----------|-----------|
| **S2.5 (Telemetry)** | Enhanced — same file, same class, backward-compatible API |
| **S7.1 (BaseAgent)** | Now creates Langfuse traces per task, has `_tracer` attribute |
| **S2.6 (LLM Router)** | Accepts `parent_handle` for nested generation logging |
| **S9.4 (Grafana)** | Prometheus metrics (unchanged) complement Langfuse's LLM-specific tracing |
| **S8.3 (Scenario Runner)** | Can pass `session_id` to group all traces for a scenario run |

## Interview Talking Points

**Q: Why hierarchical tracing instead of flat traces?**
A: A disaster response task involves one agent making 3-5 LLM calls across multiple graph nodes. Flat traces show "5 LLM calls happened" — hierarchical traces show "the situation analysis task called DeepSeek for initial assessment, then Qwen Flash for classification, nested within the 'analyze' graph node." This is the difference between "we have observability" and "we can actually debug production issues."

**Q: Why is graceful degradation so important for tracing?**
A: Tracing is observability infrastructure — it should never be the cause of a production incident. If Langfuse is down and our try/except wasn't there, every agent task would fail with a connection error. The disaster response system would stop responding to actual disasters because the monitoring tool was offline. That's the worst kind of irony.

**Q: How does prompt versioning help with evaluation?**
A: When benchmark scores change, the first question is "did the prompt change or did the model change?" Prompt versioning in Langfuse gives us an audit trail: version 1 of the orchestrator prompt scored 72 DRS, version 2 scored 78 DRS. Without this, we'd be doing git archaeology to correlate prompt changes with score changes.
