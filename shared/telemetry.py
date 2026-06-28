"""
Langfuse telemetry via the official Langfuse Python SDK.

The SDK initialises its own OTel TracerProvider that pipes spans to Langfuse.
Calling setup_langfuse() BEFORE any crewai import means CrewAI's own OTel spans
flow to Langfuse automatically (CrewAI skips installing its own provider when it
finds one already registered).

Required env vars:
    LANGFUSE_PUBLIC_KEY   pk-lf-…
    LANGFUSE_SECRET_KEY   sk-lf-…

Optional:
    LANGFUSE_HOST         default: https://cloud.langfuse.com
                          US region:  https://us.cloud.langfuse.com
"""

from __future__ import annotations

import base64
import os
import urllib.error
import urllib.request

_client = None  # langfuse.Langfuse instance, set once


def setup_langfuse() -> tuple[bool, str]:
    """
    Probe credentials then initialise the Langfuse SDK client.

    Returns (ok, error_message):
      (True,  "")        — configured and credentials valid
      (False, "")        — no keys, tracing skipped silently
      (False, "message") — keys set but invalid / unreachable
    Must be called before any crewai import.
    """
    global _client
    if _client is not None:
        return True, ""

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return False, ""

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()

    probe_error = _probe_credentials(host, auth)
    if probe_error:
        return False, probe_error

    try:
        from langfuse import Langfuse
        # SDK installs its own OTel TracerProvider — must happen before crewai.
        _client = Langfuse(public_key=pk, secret_key=sk, host=host)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def get_langfuse():
    """Return the Langfuse client, or None if not configured."""
    return _client


def flush() -> None:
    """Flush buffered spans to Langfuse (call before process exit)."""
    if _client is not None:
        try:
            _client.flush()
        except Exception:
            pass


def wire_crewai_events(crewai_event_bus) -> None:
    """Subscribe to crewai event bus and create Langfuse OTel spans for each LLM call.

    Must be called AFTER setup_langfuse() and AFTER crewai is imported.
    No-op if Langfuse is not configured.
    """
    if _client is None:
        return

    import json as _json
    from opentelemetry import trace as otel_trace
    from langfuse import LangfuseOtelSpanAttributes as A
    from crewai.events.types.llm_events import (
        LLMCallStartedEvent,
        LLMCallCompletedEvent,
        LLMCallFailedEvent,
    )
    from crewai.events.types.crew_events import (
        CrewKickoffStartedEvent,
        CrewKickoffCompletedEvent,
        CrewKickoffFailedEvent,
    )

    tracer = otel_trace.get_tracer("code-crew")
    _crew_spans: dict[str, object] = {}   # crew_name → root OTel Span
    _gen_spans: dict[str, object] = {}    # call_id   → generation OTel Span

    @crewai_event_bus.on(CrewKickoffStartedEvent)
    def _crew_start(source, event):
        span = tracer.start_span(
            name=event.crew_name or "crew-run",
            attributes={A.TRACE_NAME: event.crew_name or "crew-run"},
        )
        _crew_spans[event.crew_name or "_"] = span

    @crewai_event_bus.on(CrewKickoffCompletedEvent)
    def _crew_done(source, event):
        span = _crew_spans.pop(event.crew_name or "_", None)
        if span:
            try:
                span.set_attribute(A.TRACE_OUTPUT, str(event.output or "")[:2000])
            except Exception:
                pass
            span.end()

    @crewai_event_bus.on(CrewKickoffFailedEvent)
    def _crew_failed(source, event):
        span = _crew_spans.pop(event.crew_name or "_", None)
        if span:
            try:
                span.set_attribute(A.OBSERVATION_LEVEL, "ERROR")
                span.set_attribute(A.OBSERVATION_STATUS_MESSAGE, str(event.error or "")[:500])
            except Exception:
                pass
            span.end()

    @crewai_event_bus.on(LLMCallStartedEvent)
    def _llm_start(source, event):
        parent = next(iter(_crew_spans.values()), None)
        ctx = otel_trace.set_span_in_context(parent) if parent else None
        try:
            inp = (
                _json.dumps(event.messages, default=str)
                if not isinstance(event.messages, str)
                else event.messages
            )
        except Exception:
            inp = str(event.messages)
        span = tracer.start_span(
            name=f"llm/{event.model or 'call'}",
            context=ctx,
            attributes={
                A.OBSERVATION_TYPE: "GENERATION",
                A.OBSERVATION_MODEL: event.model or "",
                A.OBSERVATION_INPUT: inp[:4000],
            },
        )
        _gen_spans[event.call_id] = span

    @crewai_event_bus.on(LLMCallCompletedEvent)
    def _llm_done(source, event):
        span = _gen_spans.pop(event.call_id, None)
        if not span:
            return
        try:
            span.set_attribute(A.OBSERVATION_OUTPUT, str(event.response or "")[:4000])
            if event.usage:
                span.set_attribute(A.OBSERVATION_USAGE_DETAILS, _json.dumps(event.usage))
        except Exception:
            pass
        span.end()

    @crewai_event_bus.on(LLMCallFailedEvent)
    def _llm_failed(source, event):
        span = _gen_spans.pop(event.call_id, None)
        if span:
            try:
                span.set_attribute(A.OBSERVATION_LEVEL, "ERROR")
                span.set_attribute(A.OBSERVATION_STATUS_MESSAGE, str(event.error or "")[:500])
            except Exception:
                pass
            span.end()


def _probe_credentials(host: str, auth: str) -> str:
    """
    Quick credential check against the Langfuse REST API.
    Returns "" on success, an error string on failure.
    Network errors are treated as warnings (client still initialises).
    """
    url = f"{host}/api/public/traces?limit=1"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                return ""
            return f"unexpected status {resp.status}"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return (
                f"invalid credentials — check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY "
                f"and LANGFUSE_HOST ({host})"
            )
        if exc.code == 403:
            return "forbidden — key may lack required permissions (HTTP 403)"
        return f"HTTP {exc.code} from {host}"
    except Exception:
        return ""  # network unreachable — don't block startup
