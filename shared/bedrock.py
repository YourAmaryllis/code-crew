"""
Backward-compatible shim — delegates to shared.llm_factory.

Existing imports of `from shared.bedrock import get_llm_for_tier` continue to work.
New code should import from shared.llm_factory directly.
"""

from shared.llm_factory import (  # noqa: F401
    ModelTier,
    get_fast_llm,
    get_llm,
    get_llm_for_tier,
    get_powerful_llm,
)
