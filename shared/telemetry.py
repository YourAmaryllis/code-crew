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
                          US region:  https://us.cloud.langfuse.com
"""

from __future__ import annotations

import base64
import os
import urllib.error
import urllib.request

_langfuse_enabled = False


def setup_langfuse() -> tuple[bool, str]:
    """
    Probe Langfuse credentials, then install an OTLP TracerProvider.

    Returns (ok, error_message):
      (True,  "")          — configured and credentials valid
      (False, "")          — no keys set, tracing skipped silently
      (False, "message")   — keys set but invalid / unreachable
    Must be called before any crewai import.
    """
    global _langfuse_enabled
    if _langfuse_enabled:
        return True, ""

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return False, ""

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()

    # Probe credentials before installing the provider so startup shows the
    # error immediately rather than silently dropping spans later.
    probe_error = _probe_credentials(host, auth)
    if probe_error:
        return False, probe_error

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False, "opentelemetry packages not installed (pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http)"

    endpoint = f"{host}/api/public/otel/v1/traces"
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Basic {auth}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Always install ours — must pre-empt CrewAI's own provider.
    trace.set_tracer_provider(provider)

    # Flush + shutdown on exit so BatchSpanProcessor doesn't drop in-flight spans.
    import atexit
    atexit.register(lambda: provider.force_flush(timeout_millis=5000))
    atexit.register(provider.shutdown)

    _langfuse_enabled = True
    return True, ""


def _probe_credentials(host: str, auth: str) -> str:
    """
    Quick credential check against the Langfuse REST API.
    Returns "" on success, an error string on failure.
    Network errors are treated as warnings (provider still installs).
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
            return f"invalid credentials — check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY and LANGFUSE_HOST ({host})"
        if exc.code == 403:
            return f"forbidden — key may lack required permissions (HTTP 403)"
        return f"HTTP {exc.code} from {host}"
    except Exception:
        # Network unreachable, DNS failure, timeout — don't block startup.
        return ""
