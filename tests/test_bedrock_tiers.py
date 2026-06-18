"""Tests for shared.bedrock tier selection and shared.okf_loader model field."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from shared.bedrock import get_llm_for_tier


# ---------------------------------------------------------------------------
# get_llm_for_tier routing
# ---------------------------------------------------------------------------

def _env(standard="s-model", fast="f-model", powerful="p-model"):
    return {
        "BEDROCK_MODEL_ID": standard,
        "BEDROCK_FAST_MODEL_ID": fast,
        "BEDROCK_POWERFUL_MODEL_ID": powerful,
        "BEDROCK_REGION": "us-east-1",
    }


@pytest.mark.parametrize("tier,expected_id", [
    ("fast",     "f-model"),
    ("standard", "s-model"),
    ("powerful", "p-model"),
    ("unknown",  "s-model"),   # falls back to standard
    ("",         "s-model"),
])
def test_tier_selects_correct_model(tier, expected_id):
    with patch.dict(os.environ, _env(), clear=False):
        with patch("shared.bedrock._make_llm") as mock_make:
            mock_make.return_value = MagicMock()
            get_llm_for_tier(tier)
            mock_make.assert_called_once_with(expected_id)


def test_fast_falls_back_to_standard_when_not_set():
    env = {"BEDROCK_MODEL_ID": "s-model", "BEDROCK_REGION": "us-east-1"}
    with patch.dict(os.environ, env, clear=True):
        with patch("shared.bedrock._make_llm") as mock_make:
            mock_make.return_value = MagicMock()
            get_llm_for_tier("fast")
            mock_make.assert_called_once_with("s-model")


def test_powerful_falls_back_to_standard_when_not_set():
    env = {"BEDROCK_MODEL_ID": "s-model", "BEDROCK_REGION": "us-east-1"}
    with patch.dict(os.environ, env, clear=True):
        with patch("shared.bedrock._make_llm") as mock_make:
            mock_make.return_value = MagicMock()
            get_llm_for_tier("powerful")
            mock_make.assert_called_once_with("s-model")


# ---------------------------------------------------------------------------
# AgentConcept.model field parsed from OKF
# ---------------------------------------------------------------------------

def test_agent_concept_model_field(tmp_path):
    from shared.okf_loader import AgentConcept
    okf = tmp_path / "reviewer.md"
    okf.write_text(
        "---\n"
        "title: Reviewer\n"
        "description: Test reviewer\n"
        "role: Reviewer\n"
        "goal: Review things\n"
        "model: powerful\n"
        "tags: [review]\n"
        "---\n\n"
        "Backstory here.\n"
    )
    concept = AgentConcept.from_file(okf)
    assert concept.model == "powerful"


def test_agent_concept_model_defaults_to_standard(tmp_path):
    from shared.okf_loader import AgentConcept
    okf = tmp_path / "dev.md"
    okf.write_text(
        "---\n"
        "title: Dev\n"
        "description: Developer\n"
        "role: Developer\n"
        "goal: Build things\n"
        "tags: [dev]\n"
        "---\n\n"
        "Backstory.\n"
    )
    concept = AgentConcept.from_file(okf)
    assert concept.model == "standard"


def test_real_agent_okfs_have_model_field():
    """Verify every agent OKF in code_crew/knowledge/agents/ declares a model tier."""
    from shared.okf_loader import load_bundle_agents
    agents_dir = Path(__file__).parent.parent / "code_crew" / "knowledge" / "agents"
    if not agents_dir.exists():
        pytest.skip("agents directory not found")
    agents = load_bundle_agents(agents_dir)
    valid_tiers = {"fast", "standard", "powerful"}
    for name, concept in agents.items():
        assert concept.model in valid_tiers, (
            f"Agent '{name}' has invalid model tier '{concept.model}'. "
            f"Must be one of: {valid_tiers}"
        )


def test_reviewer_agents_use_powerful():
    """tech_lead and security_reviewer must be powerful tier."""
    from shared.okf_loader import load_bundle_agents
    agents_dir = Path(__file__).parent.parent / "code_crew" / "knowledge" / "agents"
    if not agents_dir.exists():
        pytest.skip("agents directory not found")
    agents = load_bundle_agents(agents_dir)
    for name in ("tech_lead", "security_reviewer"):
        if name in agents:
            assert agents[name].model == "powerful", (
                f"'{name}' should be powerful tier (it reviews others' output)"
            )


def test_scrum_master_uses_fast():
    from shared.okf_loader import load_bundle_agents
    agents_dir = Path(__file__).parent.parent / "code_crew" / "knowledge" / "agents"
    if not agents_dir.exists():
        pytest.skip("agents directory not found")
    agents = load_bundle_agents(agents_dir)
    if "scrum_master" in agents:
        assert agents["scrum_master"].model == "fast"
