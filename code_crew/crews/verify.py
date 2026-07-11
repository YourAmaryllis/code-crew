"""
Verify command crew builders and pre-checks.

build_verify_crew runs the 6-task /verify scan (arch, security, compliance,
domain, chief review, report). _precheck_security and _precheck_architecture
run deterministic Python checks before the LLM scan.
"""

from code_crew.crew import (
    _VERIFY_TASK_AGENTS,
    _parse_arch_components,
    _validate_tmd,
    _precheck_security,
    _precheck_architecture,
    build_verify_crew,
)

__all__ = [
    "_VERIFY_TASK_AGENTS",
    "_parse_arch_components",
    "_validate_tmd",
    "_precheck_security",
    "_precheck_architecture",
    "build_verify_crew",
]
