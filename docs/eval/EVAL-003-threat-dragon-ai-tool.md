# EVAL-003: InfosecOTB threat-dragon-ai-tool

**Status:** Partially adopted — multi-pass refinement concept adopted; tool itself not adopted
**Date:** 2026-07-07
**Related:**
- [ADD-008: Incremental Per-Unit LLM Decomposition](../add/ADD-008-Incremental-Per-Unit-LLM-Decomposition.md)
- [ADD-011: Multi-Pass Threat Model Refinement](../add/ADD-011-Multi-Pass-Threat-Model-Refinement.md)

---

InfosecOTB/threat-dragon-ai-tool (github.com/InfosecOTB/threat-dragon-ai-tool) is a Python desktop app that uses an LLM to generate STRIDE threats and mitigations for existing OWASP Threat Dragon data-flow diagrams. It was published in early 2026 alongside a two-part tutorial series on AI-powered threat modelling with OWASP Threat Dragon. The OWASP Threat Dragon community has proposed integrating it natively into Threat Dragon's desktop menu (discussion #1358).

---

## What threat-dragon-ai-tool is

**Workflow: DFD-first → AI adds threats**

1. User draws a Data Flow Diagram in OWASP Threat Dragon (desktop or web)
2. Tool reads the Threat Dragon `.json` model file
3. Injects the full DFD + OWASP STRIDE schema into an LLM system prompt via LiteLLM
4. LLM outputs structured STRIDE threats and mitigations (Pydantic-validated JSON)
5. Tool writes threats and red-stroke visual indicators back into the `.json` file
6. User reopens the file in Threat Dragon to review

Key properties:
- **STRIDE only** — no LINDDUN, DIE, or PLOT4ai support
- **Multi-LLM** via LiteLLM — OpenAI, Anthropic, Google, xAI, Ollama; any `provider/model` string
- **Iterative refinement** — can run multiple passes; the LLM reviews existing threats before adding new ones, avoiding duplication
- **GUI** — ttkbootstrap desktop application, API key stored in system keyring
- **Pydantic validation** — structured JSON output schema enforced on every LLM response
- **Requires closing Threat Dragon** before running; user re-opens the file to see results

---

## Architecture comparison

| Dimension | threat-dragon-ai-tool | code-crew `/threat` |
|---|---|---|
| Input | Human-drawn Threat Dragon DFD (`.json`) | Source code + IaC + design docs (codebase) |
| Architecture discovery | None — user provides it | Agents discover it from source files |
| Output format | Threat Dragon JSON (threats written back in-place) | OTM YAML → Threat Dragon JSON (via `threat_model_export.py`) |
| DFD generation | User draws it manually | Agents generate it as part of OTM |
| Threat frameworks | STRIDE only | STRIDE + LINDDUN (PHI) + DIE (containers) + PLOT4ai (LLM) |
| Multi-agent | No — single LLM call per run | Yes — Security Lead + Architect manager-worker |
| Iterative refinement | Yes — explicit multi-pass design | No — single pass per component (ADD-008 pattern) |
| LLM backend | LiteLLM (any provider) | NVIDIA Build / Bedrock |
| Structured output | Pydantic validation | `_parse_yaml_section` extraction |
| Scope | Individual team drawing DFDs | Enterprise pipeline from code to OTM |

---

## What threat-dragon-ai-tool does better

**Iterative refinement by design.** The tool's explicit multi-pass model — where each pass reads the existing threats and adds only what's missing — means the output improves incrementally with each run. The user can run it, review, and trigger another pass without starting over. code-crew's threat flow runs once per component and has no equivalent mechanism.

**Zero-friction for DFD-owning teams.** Teams that already maintain Threat Dragon diagrams get AI-generated STRIDE threats in one click. No codebase access required, no agent pipeline to configure.

**Provider agnosticism.** LiteLLM supports any OpenAI-compatible provider with a single `provider/model` string. Switching models requires only a config change.

---

## What code-crew does better

**No diagram required.** The Security Lead and Architect agents discover the system architecture directly from source files, dependency manifests, Terraform, and design docs. Teams with no existing DFD get a complete OTM including the diagram.

**Multi-framework coverage.** LINDDUN for PHI-handling components, DIE for ECS tasks and Lambdas, and PLOT4ai for LLM endpoints are applied automatically based on component type. threat-dragon-ai-tool produces STRIDE threats only — an LLM endpoint or a PHI store gets the same six-category analysis as a simple API.

**OWASP four-question process.** The Security Lead drives the session through all four OWASP Threat Modeling Process questions (What are we building? What can go wrong? What are we doing about it? Did we do a good job?). The gate enforces structural completeness before accepting the output.

**Integrated review gate.** The manager gate validates zone semantics, component naming, framework coverage, and mitigation state before the OTM is written to disk. threat-dragon-ai-tool has no equivalent quality check.

**Code-aware context.** Agents know the encryption flags, IAM policies, and protocol choices in the actual code — not just what the diagram labels say. A Threat Dragon flow labelled "HTTPS" that actually uses plain HTTP in the code will be caught.

---

## What we are adopting: iterative multi-pass refinement

The core insight from threat-dragon-ai-tool worth carrying forward is the **multi-pass model**: run the threat analysis more than once over the assembled output, with each pass reading existing threats and adding what's missing rather than regenerating from scratch.

In code-crew's context this addresses a known gap in the ADD-008 per-unit pattern: the per-component analysis is good at intra-component threats but systematically misses:

1. **Trust boundary crossing threats** — a threat that spans two components in different zones only becomes visible when both components and their connecting dataflows are analysed together
2. **Threat chaining** — an attacker who exploits T-001 to gain access then uses that access to execute T-015 on a different component; the per-unit pass sees each threat independently
3. **Compound framework gaps** — a component tagged `phi_involved: true` with `type: ecs-task` needs LINDDUN + DIE coverage; the per-unit pass may produce one framework's threats and miss the other

A second pass that reads the complete assembled OTM and outputs only the additional threats and mitigations missing from Pass 1 closes this gap without re-running the expensive per-component work.

The design for this is in [ADD-011](../add/ADD-011-Multi-Pass-Threat-Model-Refinement.md).

---

## What we are not adopting

**The tool itself.** The integration path is awkward: we'd need to export OTM → Threat Dragon JSON, run their tool to add STRIDE threats, then import those threats back into OTM format. The round-trip is lossy (they write in TD JSON, not OTM) and duplicates threat generation we already do.

**LiteLLM as the primary backend.** code-crew's LLM routing (NVIDIA Build / Bedrock) is already handled by `shared/llm_factory.py`. Adding LiteLLM as another abstraction layer adds a dependency without changing capability. If multi-provider support becomes a requirement, LiteLLM is worth revisiting at the `llm_factory` level.

**STRIDE-only scope.** The tool's methodology ceiling is STRIDE. For a platform with PHI-handling components and LLM endpoints, capping at STRIDE would produce materially incomplete threat models.

---

## Decision

The tool is not adopted. The multi-pass refinement pattern it demonstrated is adopted as the design for `threat_refine` — a new task and flow phase that runs after the ADD-008 per-unit pipeline and adds cross-component and cross-boundary threats to the assembled OTM. See ADD-011 for the full design.
