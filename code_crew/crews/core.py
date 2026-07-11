"""
Shared utilities used across all command areas.

Re-exports from crew.py: LLM helpers, agent/task builders, context formatters,
structure loaders, and skill loaders.
"""

from code_crew.crew import (
    # Module-level constant
    _KNOWLEDGE,

    # Tool / agent / task factories
    _load_stacks,
    _kickoff,
    _mcp_tools_for,
    _make_tools,
    build_agents,
    _make_guardrail,
    _make_ci_guardrail,
    _impl_guardrail,
    build_tasks,
    MANAGED_TASKS,
    _STANDARD_MANAGER_TASKS,
    _build_manager_agent,

    # Context formatters
    _resolved_designs_path,
    _designs_context_line,
    _format_design_context,
    _format_context,

    # Structure loaders
    _load_project_structure,
    _load_structure_sections,
    _load_decomposition_diagram,
    STRUCTURE_SECURITY,
    STRUCTURE_DEVOPS,
    STRUCTURE_ENGINEER,

    # Skill loaders
    _skill_search_dirs,
    _find_skill,
    _strip_frontmatter,
    _load_active_skills,

    # LLM call helpers
    _crew_kickoff_with_timeout,
    _llm_call,
    _llm_call_with_tools,
)

__all__ = [
    "_KNOWLEDGE",
    "_load_stacks",
    "_kickoff",
    "_mcp_tools_for",
    "_make_tools",
    "build_agents",
    "_make_guardrail",
    "_make_ci_guardrail",
    "_impl_guardrail",
    "build_tasks",
    "MANAGED_TASKS",
    "_STANDARD_MANAGER_TASKS",
    "_build_manager_agent",
    "_resolved_designs_path",
    "_designs_context_line",
    "_format_design_context",
    "_format_context",
    "_load_project_structure",
    "_load_structure_sections",
    "_load_decomposition_diagram",
    "STRUCTURE_SECURITY",
    "STRUCTURE_DEVOPS",
    "STRUCTURE_ENGINEER",
    "_skill_search_dirs",
    "_find_skill",
    "_strip_frontmatter",
    "_load_active_skills",
    "_crew_kickoff_with_timeout",
    "_llm_call",
    "_llm_call_with_tools",
]
