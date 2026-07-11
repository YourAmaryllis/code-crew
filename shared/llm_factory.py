"""
Multi-provider LLM factory for code-crew.

Config hierarchy (highest priority first):
  1. Agent override  — llm.agents.<name>.provider / .model
  2. Tier override   — llm.tiers.<tier>.provider / .model
  3. Default         — llm.default.provider / .model
  4. Legacy Bedrock env vars (BEDROCK_MODEL_ID, etc.) — always available as fallback

Config is loaded from ~/.code-crew/config.yaml llm: section into LLM_CONFIG env var (JSON).

Provider → LiteLLM model string format:
  bedrock    → "bedrock/<model_id>"     requires: AWS credentials
  anthropic  → "anthropic/<model>"      requires: ANTHROPIC_API_KEY
  openai     → "openai/<model>"         requires: OPENAI_API_KEY
  groq       → "groq/<model>"           requires: GROQ_API_KEY
  ollama     → "ollama/<model>"         requires: Ollama running locally
  nvidia     → OpenAI-compat at https://integrate.api.nvidia.com/v1
                                        requires: NVIDIA_API_KEY (nvapi-...)
"""

from __future__ import annotations

import json
import os
from typing import Literal

from crewai import LLM

ModelTier = Literal["fast", "standard", "powerful"]

# Context window sizes (tokens) for NVIDIA Build models.
# CrewAI's built-in lookup table doesn't know these model strings, so it
# defaults to ~9k. Setting the correct value lets CrewAI trim context before
# it sends an oversized request that causes a 504 gateway timeout.
_NVIDIA_CONTEXT_WINDOWS: dict[str, int] = {
    "meta/llama-3.1-8b-instruct": 128_000,
    "meta/llama-3.1-70b-instruct": 128_000,
    "meta/llama-3.3-70b-instruct": 128_000,
    "meta/llama-3.1-405b-instruct": 128_000,
    # nvidia/llama-3.1-nemotron-70b-instruct removed from free tier (404 as of 2026-07)
    "nvidia/llama-3.3-nemotron-super-49b-v1": 131_072,
    # nemotron-3-super and nemotron-4-340b are mixture-of-experts models with
    # tiny effective context windows — do NOT use for tasks that carry large OTMs.
    "nvidia/nemotron-3-super-120b-a12b": 4_096,
    "nvidia/nemotron-4-340b-instruct": 4_096,
    "mistralai/mixtral-8x22b-instruct-v0.1": 65_536,
    "mistralai/mistral-7b-instruct-v0.3": 32_768,
    "google/gemma-3-27b-it": 131_072,
    "moonshotai/kimi-k2.6": 131_072,
    "microsoft/phi-4-14b": 16_384,
}


def _llm_config() -> dict:
    """Return parsed llm: config. Falls back to legacy Bedrock env vars."""
    raw = os.environ.get("LLM_CONFIG", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # Legacy Bedrock fallback — always works if BEDROCK_MODEL_ID is set
    std = os.environ.get("BEDROCK_MODEL_ID", "")
    return {
        "default": {"provider": "bedrock", "model": std},
        "tiers": {
            "fast":     {"provider": "bedrock", "model": os.environ.get("BEDROCK_FAST_MODEL_ID", std)},
            "standard": {"provider": "bedrock", "model": std},
            "powerful": {"provider": "bedrock", "model": os.environ.get("BEDROCK_POWERFUL_MODEL_ID", std)},
        },
    }


def _resolve(tier: str, agent_name: str = "") -> tuple[str, str]:
    """Return (provider, model) for the given tier and optional agent name."""
    cfg = _llm_config()

    # 1. Agent override
    if agent_name:
        agent_cfg = cfg.get("agents", {}).get(agent_name, {})
        if agent_cfg.get("provider") and agent_cfg.get("model"):
            return agent_cfg["provider"], agent_cfg["model"]

    # 2. Tier override
    tier_cfg = cfg.get("tiers", {}).get(tier, {})
    if tier_cfg.get("provider") and tier_cfg.get("model"):
        return tier_cfg["provider"], tier_cfg["model"]

    # 3. Default
    default = cfg.get("default", {})
    provider = default.get("provider", "bedrock")
    model = default.get("model", os.environ.get("BEDROCK_MODEL_ID", ""))
    return provider, model


def _make_llm(provider: str, model: str) -> LLM:
    # LiteLLM expects "provider/model" unless the model already contains a "/"
    # that isn't just the provider prefix.
    if provider == "bedrock":
        model_str = f"bedrock/{model}" if not model.startswith("bedrock/") else model
        return LLM(
            model=model_str,
            aws_region_name=os.environ.get("BEDROCK_REGION", "us-east-1"),
            temperature=float(os.environ.get("BEDROCK_TEMPERATURE", "0.2")),
            **_bedrock_guardrail_kwargs(),
        )

    if provider == "nvidia":
        # NVIDIA Build — OpenAI-compatible; provider="openai" bypasses CrewAI's
        # model whitelist check so custom model names (meta/llama-...) are accepted.
        # timeout=120: NVIDIA free tier silently hangs instead of returning 504;
        # a 2-minute HTTP timeout lets LiteLLM raise ReadTimeout so the retry
        # logic in _llm_call can kick in.
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        context_window = _NVIDIA_CONTEXT_WINDOWS.get(model, 128_000)
        llm = LLM(
            model=model,
            provider="openai",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            temperature=0.2,
            timeout=120,
        )
        # CrewAI routes nvidia through OpenAICompletion whose get_context_window_size()
        # only knows GPT model names and falls back to ~8k for everything else.
        # Override it so CrewAI trims context at the correct limit for this model.
        llm.get_context_window_size = lambda: context_window
        return llm

    # All other providers: just prefix and pass temperature
    prefix_map = {"anthropic": "anthropic", "openai": "openai", "groq": "groq", "ollama": "ollama"}
    prefix = prefix_map.get(provider, provider)
    model_str = f"{prefix}/{model}" if not model.startswith(f"{prefix}/") else model
    return LLM(model=model_str, temperature=0.2)


def _bedrock_guardrail_kwargs() -> dict:
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
    if not guardrail_id:
        return {}
    return {
        "additional_model_request_fields": {
            "guardrailConfig": {
                "guardrailIdentifier": guardrail_id,
                "guardrailVersion": os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
                "trace": "enabled",
            }
        }
    }


def get_llm_for_tier(tier: ModelTier | str, agent_name: str = "") -> LLM:
    """Return the LLM for the given tier, with optional per-agent override."""
    provider, model = _resolve(tier, agent_name)
    if not model:
        raise RuntimeError(
            f"No model configured for tier={tier!r} agent={agent_name!r}. "
            "Set BEDROCK_MODEL_ID or add llm: section to ~/.code-crew/config.yaml"
        )
    return _make_llm(provider, model)


def direct_llm_completion(prompt: str, tier: str = "fast",
                           timeout: int = 90, max_retries: int = 3) -> str:
    """Call the LLM directly without CrewAI, with a real socket-level timeout.

    CrewAI/LiteLLM wrap the HTTP client in ways that prevent timeout enforcement
    on some providers (NVIDIA free tier silently hangs). This function uses the
    OpenAI Python client directly for OpenAI-compatible providers, which enforces
    the httpx timeout at the socket level. Falls back to litellm for other providers.

    Use this for simple, single-shot LLM calls where agent wrapping is unnecessary.
    """
    import time

    provider, model = _resolve(tier)
    last_exc: BaseException | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 30 * attempt
            print(f"  [direct_llm retry {attempt}/{max_retries}] waiting {wait}s…")
            time.sleep(wait)
        try:
            if provider in ("nvidia", "openai", "anthropic", "groq"):
                from openai import OpenAI

                kwargs: dict = {
                    "timeout": timeout,
                }
                if provider == "nvidia":
                    kwargs["api_key"] = os.environ.get("NVIDIA_API_KEY", "")
                    kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
                elif provider == "openai":
                    kwargs["api_key"] = os.environ.get("OPENAI_API_KEY", "")
                elif provider == "groq":
                    from openai import OpenAI as _OAI  # groq also OpenAI-compat
                    kwargs["api_key"] = os.environ.get("GROQ_API_KEY", "")
                    kwargs["base_url"] = "https://api.groq.com/openai/v1"

                client = OpenAI(**kwargs)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                return resp.choices[0].message.content or ""

            else:
                # Bedrock, Ollama, etc. — fall back to litellm
                import litellm

                prefix_map = {"bedrock": "bedrock", "ollama": "ollama"}
                prefix = prefix_map.get(provider, provider)
                model_str = f"{prefix}/{model}" if not model.startswith(f"{prefix}/") else model
                resp = litellm.completion(
                    model=model_str,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    request_timeout=timeout,
                )
                return resp.choices[0].message.content or ""

        except BaseException as exc:
            last_exc = exc
            print(f"  direct_llm attempt {attempt + 1} failed: {exc}")

    raise RuntimeError(
        f"direct_llm_completion failed after {max_retries + 1} attempts"
    ) from last_exc


# Convenience aliases kept for callers that import directly
def get_llm() -> LLM:
    return get_llm_for_tier("standard")


def get_fast_llm() -> LLM:
    return get_llm_for_tier("fast")


def get_powerful_llm() -> LLM:
    return get_llm_for_tier("powerful")
