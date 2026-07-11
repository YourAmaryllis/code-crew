"""
Threat modeling command crew builders.

These functions implement the /threat command: OTM scope decision,
per-component threat/mitigation analysis, OTM assembly, gate review,
and patch loop.
"""

from code_crew.crew import (
    build_otm_scope_task,
    _MAX_PRE_READ_BYTES,
    _MAX_PRE_READ_FILES,
    _MAX_TERRAFORM_LINES,
    _pre_read,
    _terraform_grep,
    _build_threat_context,
    build_threat_model_crew,
    build_threat_patch_crew,
    build_threat_gate_crew,
    _parse_yaml_section,
    _infer_assets,
    _infer_dataflows,
    assemble_otm_yaml,
    build_threat_discover_crew,
    build_threat_component_threats_crew,
    build_threat_component_crew,
    build_threat_mitigations_crew,
)

__all__ = [
    "build_otm_scope_task",
    "_MAX_PRE_READ_BYTES",
    "_MAX_PRE_READ_FILES",
    "_MAX_TERRAFORM_LINES",
    "_pre_read",
    "_terraform_grep",
    "_build_threat_context",
    "build_threat_model_crew",
    "build_threat_patch_crew",
    "build_threat_gate_crew",
    "_parse_yaml_section",
    "_infer_assets",
    "_infer_dataflows",
    "assemble_otm_yaml",
    "build_threat_discover_crew",
    "build_threat_component_threats_crew",
    "build_threat_component_crew",
    "build_threat_mitigations_crew",
]
