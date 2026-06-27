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
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        return LLM(
            model=model,
            provider="openai",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            temperature=0.2,
        )

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


# Convenience aliases kept for callers that import directly
def get_llm() -> LLM:
    return get_llm_for_tier("standard")


def get_fast_llm() -> LLM:
    return get_llm_for_tier("fast")


def get_powerful_llm() -> LLM:
    return get_llm_for_tier("powerful")
