"""
CrewAI LLM factory for Amazon Bedrock (Claude).

Configuration via environment variables — no hardcoded model IDs or regions.
See .env.example for required variables.

Three tiers, each maps to one env var:
  fast      → BEDROCK_FAST_MODEL_ID     (default: falls back to standard)
  standard  → BEDROCK_MODEL_ID          (required)
  powerful  → BEDROCK_POWERFUL_MODEL_ID (default: falls back to standard)

Use get_llm_for_tier(tier) when the tier comes from an agent OKF.
"""

import os
from typing import Literal

from crewai import LLM

ModelTier = Literal["fast", "standard", "powerful"]


def get_llm() -> LLM:
    """Standard tier — balanced cost/quality. Used by implementation agents."""
    return _make_llm(os.environ["BEDROCK_MODEL_ID"])


def get_fast_llm() -> LLM:
    """Fast/cheap tier for lightweight tasks (planning checks, index reads)."""
    model_id = os.environ.get("BEDROCK_FAST_MODEL_ID") or os.environ["BEDROCK_MODEL_ID"]
    return _make_llm(model_id)


def get_powerful_llm() -> LLM:
    """Powerful tier for review agents that verify lower-tier output."""
    model_id = os.environ.get("BEDROCK_POWERFUL_MODEL_ID") or os.environ["BEDROCK_MODEL_ID"]
    return _make_llm(model_id)


def get_llm_for_tier(tier: ModelTier | str) -> LLM:
    """Return the LLM for the given tier string. Unknown tiers fall back to standard."""
    if tier == "fast":
        return get_fast_llm()
    if tier == "powerful":
        return get_powerful_llm()
    return get_llm()


def _make_llm(model_id: str) -> LLM:
    return LLM(
        model=f"bedrock/{model_id}",
        aws_region_name=os.environ.get("BEDROCK_REGION", "us-east-1"),
        temperature=float(os.environ.get("BEDROCK_TEMPERATURE", "0.2")),
        **_guardrail_kwargs(),
    )


def _guardrail_kwargs() -> dict:
    """Inject Bedrock Guardrails config if BEDROCK_GUARDRAIL_ID is set."""
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    if not guardrail_id:
        return {}
    return {
        "additional_model_request_fields": {
            "guardrailConfig": {
                "guardrailIdentifier": guardrail_id,
                "guardrailVersion": guardrail_version,
                "trace": "enabled",
            }
        }
    }
