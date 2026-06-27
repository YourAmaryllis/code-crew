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
