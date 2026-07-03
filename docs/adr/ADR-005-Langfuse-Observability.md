# ADR-005: Langfuse for Agent Observability

**Status:** Accepted
**Date:** 2026-07-03
**Related:** [SAD-001](../sad/SAD-001-code-crew.md)

---

## Context

Multi-agent LLM workflows have poor debuggability by default. A failed run shows CrewAI's verbose console output — a stream of tool calls, agent reasoning, and intermediate responses — with no structured way to query which agent called which tool, how many tokens were used, which task took 10 minutes, or where the run diverged from the expected path.

Three observability options were evaluated:

| Option | Summary |
|--------|---------|
| **CrewAI's built-in Langsmith** | Requires LangSmith API key; tightly coupled to LangChain; not neutral |
| **Raw OTLP (e.g. to Grafana)** | Maximum flexibility; requires running a collector + dashboard; setup overhead for solo/small teams |
| **Langfuse** | Open-source LLM observability (self-hostable or cloud); official Python SDK; clean OTel integration; session/trace/generation hierarchy matches the crew/task/LLM-call hierarchy naturally |

CrewAI emits OTel spans for crew runs and LLM calls. The challenge is that CrewAI installs its own `TracerProvider` at import time — if the observability provider is initialised after `import crewai`, the spans go to CrewAI's own backend, not Langfuse.

## Decision

Use **Langfuse** via the official Python SDK for all agent observability.

1. `setup_langfuse()` in `shared/telemetry.py` **must be called before any `crewai` import** — the Langfuse SDK installs its own OTel `TracerProvider`; CrewAI detects the registered provider and skips installing its own, so all CrewAI spans flow to Langfuse automatically.

2. `wire_crewai_events()` subscribes to the CrewAI event bus for `CrewKickoff*` and `LLMCall*` events, creating nested OTel spans — a crew-level root span containing per-LLM-call generation spans with input/output and token usage.

3. Langfuse is **optional** — if `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are not set, `setup_langfuse()` returns `(False, "")` silently and the run proceeds without tracing. Startup banner shows `langfuse ✓` or `langfuse ✗`.

4. Credentials are **probed at startup** before the SDK is initialised — a `GET /api/public/traces?limit=1` call validates the keys. A 401 returns an actionable error. A network error is treated as a warning (keys may be valid but the network is unreachable), and the SDK initialises anyway.

5. Span content is **bounded**: input/output capped at 4 000 characters; token usage forwarded from `event.usage`. Full content is not needed for debugging; capping prevents accidental PII leakage in traces.

## Consequences

**Positive:**
- Every crew run produces a structured Langfuse trace: crew → task → LLM call hierarchy with durations, token counts, and inputs/outputs
- No LangChain dependency — Langfuse's OTel integration is provider-neutral
- Optional setup — teams that don't need observability skip configuration; the tool still runs
- Self-hostable (Langfuse is open source) — no mandatory third-party data transmission

**Negative / Risks:**
- Import ordering is a hard constraint: `setup_langfuse()` before `import crewai` — any refactor that changes `repl.py` import order can silently break tracing
- Langfuse cloud stores LLM inputs/outputs — do not set `LANGFUSE_*` keys in environments where prompt content is sensitive

**Operational:**
- Config keys: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (default: `https://cloud.langfuse.com`; US region: `https://us.cloud.langfuse.com`)
- `shared/telemetry.py` — `setup_langfuse()`, `wire_crewai_events()`, `flush()`
- `flush()` called before process exit to drain buffered spans
- Startup check: `_check_langfuse()` in `startup.py` — shown in banner as optional check

## References
- Langfuse Python SDK: https://langfuse.com/docs/sdk/python
- CrewAI OTel event bus: https://docs.crewai.com/observability
