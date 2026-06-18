"""
CrewAI LLM factory for Amazon Bedrock (Claude).

Configuration via environment variables — no hardcoded model IDs or regions.
See .env.example for required variables.
"""

import os

from crewai import LLM


def get_llm() -> LLM:
    """Primary LLM for all agents — capable, balanced cost/quality."""
    return LLM(
        model=f"bedrock/{os.environ['BEDROCK_MODEL_ID']}",
        aws_region_name=os.environ.get("BEDROCK_REGION", "us-east-1"),
        temperature=float(os.environ.get("BEDROCK_TEMPERATURE", "0.2")),
        **_guardrail_kwargs(),
    )


def get_fast_llm() -> LLM:
    """Fast/cheap LLM for lightweight tasks (planning checks, index reads)."""
    model_id = os.environ.get("BEDROCK_FAST_MODEL_ID", os.environ["BEDROCK_MODEL_ID"])
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
