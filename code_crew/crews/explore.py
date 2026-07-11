"""
Explore command crew builders and helpers.

These functions implement the /explore command: repo breakdown, per-unit
summarization, service classification, decomposition synthesis, and the
Phase 5 diagram synthesis (deployment, network, architectural DFD).
"""

from code_crew.crew import (
    _run_explore_subtask,
    _build_filtered_tree,
    build_breakdown_task,
    _pre_read_unit,
    build_summarize_unit_task,
    build_summarize_docs_task,
    _DEPLOYABLE_TYPES,
    classify_units_from_structure,
    build_diagram_from_services,
    build_synthesize_decomposition_from_structure,
    _pre_read_infra_dir,
    _pre_read_sad,
    build_synthesize_decomposition_task,
    _parse_decomposition_output,
    _pre_read_service,
    _pre_read_domain,
    build_summarize_service_task,
    build_summarize_domain_task,
    build_synthesize_scope_task,
    build_synthesize_architecture_task,
    build_synthesize_compliance_task,
    _build_summaries_context,
    build_explore_single_task,
    # Phase 5 — diagram synthesis
    _extract_connections_from_structure,
    _pre_read_network_infra,
    _extract_structure_sections,
    build_deployment_diagram_task,
    build_network_diagram_task,
    build_dataflow_diagram_task,
)

__all__ = [
    "_run_explore_subtask",
    "_build_filtered_tree",
    "build_breakdown_task",
    "_pre_read_unit",
    "build_summarize_unit_task",
    "build_summarize_docs_task",
    "_DEPLOYABLE_TYPES",
    "classify_units_from_structure",
    "build_diagram_from_services",
    "build_synthesize_decomposition_from_structure",
    "_pre_read_infra_dir",
    "_pre_read_sad",
    "build_synthesize_decomposition_task",
    "_parse_decomposition_output",
    "_pre_read_service",
    "_pre_read_domain",
    "build_summarize_service_task",
    "build_summarize_domain_task",
    "build_synthesize_scope_task",
    "build_synthesize_architecture_task",
    "build_synthesize_compliance_task",
    "_build_summaries_context",
    "build_explore_single_task",
    # Phase 5
    "_extract_connections_from_structure",
    "_pre_read_network_infra",
    "_extract_structure_sections",
    "build_deployment_diagram_task",
    "build_network_diagram_task",
    "build_dataflow_diagram_task",
]
