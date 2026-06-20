"""
Langfuse telemetry via OpenTelemetry.

CrewAI creates OTLP spans via `trace.get_tracer("crewai.telemetry")` — the
global TracerProvider.  If we install our own TracerProvider pointing at Langfuse
before CrewAI's EventListener singleton is initialised, CrewAI's set_tracer()
finds an existing (non-Proxy) provider and skips installing its own.  All spans
(crew/task/agent/LLM lifecycle) then flow to Langfuse automatically.

IMPORTANT: setup_langfuse() must be called BEFORE any crewai import, because
crewai/events/event_listener.py creates the EventListener singleton at module
level, which triggers Telemetry.set_tracer() and installs CrewAI's own provider.

Required env vars (set via profile):
    LANGFUSE_PUBLIC_KEY   pk-lf-…
    LANGFUSE_SECRET_KEY   sk-lf-…

Optional:
    LANGFUSE_HOST         default: https://cloud.langfuse.com
"""

from __future__ import annotations

import base64
import os

_langfuse_enabled = False


def setup_langfuse() -> bool:
    """
    Install an OTLP TracerProvider that exports to Langfuse.
    Returns True if configured, False if keys are absent or packages missing.
    Must be called before any crewai import.
    """
    global _langfuse_enabled
    if _langfuse_enabled:
        return True

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return False

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    endpoint = f"{host}/api/public/otel/v1/traces"
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Basic {auth}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Always install ours — if crewai hasn't run yet, we pre-empt it;
    # if crewai already ran (shouldn't happen if called first), we take over.
    trace.set_tracer_provider(provider)

    # Flush + shutdown on exit so BatchSpanProcessor doesn't drop in-flight spans.
    import atexit
    atexit.register(lambda: provider.force_flush(timeout_millis=5000))
    atexit.register(provider.shutdown)

    _langfuse_enabled = True
    return True
