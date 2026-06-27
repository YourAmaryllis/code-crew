---
type: security
title: AI/ML Security
description: Security requirements for services that include LLMs, ML models, embedding pipelines, RAG retrievers, or agent/tool-calling systems
tags: [ai, ml, llm, rag, agents, owasp-llm, plot4ai, security]
timestamp: 2026-06-26T00:00:00Z
activates:
  - plot4ai-diagrams
  - owasp-llm
---

# AI/ML Security Stack

Activate this stack when the feature or service includes any of:
- An LLM call (hosted model, Bedrock, OpenAI, Anthropic, self-hosted)
- A machine learning model for inference or classification
- An embedding generation or vector search pipeline
- A RAG (Retrieval-Augmented Generation) retriever
- An agent / tool-calling system
- A training or fine-tuning pipeline

When active, the security lead must:
1. Apply the OWASP Top 10 for LLM checklist below (in addition to the standard OWASP baseline)
2. Produce a PLOT4ai diagram in the Threat Dragon model (in addition to the STRIDE diagram)

---

## AI/ML Component Classification

| Component | Data classification | Notes |
|-----------|-------------------|-------|
| Model weights | Confidential — IP | Version-pin; sign artifacts; restrict read access |
| Training dataset | Confidential/Regulated | Track provenance; verify consent for training use |
| Embeddings / vector store | Confidential | May re-identify individuals (linkability threat) |
| Prompt templates | Internal | Treat as code; version-controlled; never user-editable at runtime |
| Model outputs / completions | Varies — audit all | Log for safety review; do not assume safe for downstream use |
| Fine-tuning labels | Confidential/Regulated | Same handling as training data |

---

## OWASP Top 10 for LLM (2025)

For each item: state PASS or FAIL with specific evidence (file, line, config, pattern found).

**LLM01 — Prompt Injection**
- User-controlled input must never be concatenated directly into a system prompt without sanitisation or structural separation
- Indirect injection: retrieved documents must not be able to override system instructions
- Tool/function call arguments derived from LLM output must be validated before execution
- Mitigation: structural prompt separation, input allowlisting for high-risk fields, human confirmation gate for privileged tool calls

**LLM02 — Sensitive Information Disclosure**
- Model must not be able to return data outside the requesting user's authorisation scope
- System prompt must not contain secrets, credentials, or PII
- Model output must be scanned for PII/PHI before returning to caller if training data included regulated content
- Retrieval results must be access-controlled before passing to the model

**LLM03 — Supply Chain**
- Model provider / version pinned in config; not resolved at runtime without approval
- Model artifacts verified (hash or signature) before loading
- Third-party plugins, tools, or agent frameworks version-pinned in lockfile
- No auto-upgrade of model versions in production

**LLM04 — Data and Model Poisoning**
- Training data sources documented and access-controlled
- Fine-tuning data reviewed for adversarial samples before use
- Model behaviour monitored post-deployment for unexpected drift
- Rollback procedure exists and is tested

**LLM05 — Improper Output Handling**
- LLM output is never passed directly to: `eval`, `exec`, shell commands, SQL, HTML render without sanitisation
- Output used to drive tool calls is validated against a schema before execution
- Output displayed to users is HTML-escaped

**LLM06 — Excessive Agency**
- Agent has only the minimum permissions needed for its task
- No agent can take irreversible actions (delete, send, publish, pay) without a human-in-the-loop confirmation gate
- Tool call scope is bounded: no open-ended shell, no unrestricted file write, no arbitrary HTTP
- Agent cannot escalate its own permissions

**LLM07 — System Prompt Confidentiality**
- System prompt must not be disclosed in model output
- Prompt injection attempts to extract system prompt are blocked
- System prompt does not contain secrets (use env vars / Secrets Manager instead)

**LLM08 — Vector and Embedding Weaknesses**
- Embedding store access is authenticated and authorised per-user/tenant
- Vectors cannot be read out to reconstruct training samples (membership inference mitigation)
- Retrieval results are filtered by the caller's authorisation before passing to the model

**LLM09 — Misinformation**
- High-stakes decisions (medical, legal, financial, safety-critical) must include a human-in-the-loop gate or explicit disclaimer
- Model outputs are not presented as authoritative without grounding/citation
- Hallucination rate is measured and within acceptable threshold for the use case

**LLM10 — Unbounded Consumption**
- Token limits enforced per request and per user/session
- Rate limiting applied to inference endpoints
- Cost anomaly alerting configured (spend spike = potential attack signal)
- Adversarial inputs designed to maximise token consumption are detected and rejected

---

## PLOT4ai Mandatory Coverage

When this stack is active, the security_lead must produce a PLOT4ai diagram. Refer to `threat-dragon` for the full schema and type definitions. Minimum coverage:

| Component | Required PLOT4ai threats |
|-----------|--------------------------|
| LLM / inference endpoint | Output Control (prompt injection), Security Breach (model extraction), Privacy Violation (PII in prompt), Accountability (decision audit log) |
| Embedding store | Privacy Violation (membership inference), Linkability (re-identification), Security Breach (poisoning) |
| Training / fine-tuning pipeline | Security Breach (data poisoning), Fairness (dataset bias), Accountability (version tracking + rollback) |
| RAG retriever | Output Control (context injection), Security Breach (retrieval manipulation), Transparency (undisclosed sources) |
| Agent / tool-calling system | Output Control (unsafe tool invocation), Accountability (tool call audit trail), Availability (runaway loops) |
| Model registry | Security Breach (supply chain), Accountability (unsigned artifacts), Availability (model deletion) |

---

## Model Lifecycle Security

**Version pinning**: Every model reference in code or config must specify an exact version identifier (model ID, hash, or tag). No `latest`.

**Artifact signing**: Model weights and fine-tuned checkpoints must be signed and verified before loading in staging or production.

**Drift detection**: Monitor model output distribution post-deployment. Alert on significant drift (possible poisoning or capability regression).

**Rollback**: A rollback procedure to the previous model version must exist and be tested at least once before production deployment.

**Deprecation**: When a model version is retired, audit all callers to ensure they migrate before the provider end-of-life date.

---

## Data Lineage and Consent

- Training dataset sources must be documented (origin, license, collection date)
- If the dataset includes user-generated content, verify consent for training use
- PII in training data must be anonymised or pseudonymised before training
- Data retention period for training artifacts must align with the active compliance framework (GDPR Art.5, HIPAA §164.312)

---

## Output Governance

- All model inputs and outputs must be logged with a request ID, user ID (or session ID), model version, and timestamp
- Logs must be retained per the active compliance framework's audit evidence requirements
- For high-stakes decisions: output must be reviewed by a human before action is taken, or the decision must be clearly marked as AI-generated with a disclaimer
- Output safety filtering: apply a content classifier or guardrail before returning output in consumer-facing products

---

## Review Output Format

Security lead output when this stack is active (append to standard security review):

```
AI/ML SECURITY REVIEW

OWASP LLM Top 10:
  LLM01 Prompt Injection:        PASS / FAIL — <evidence>
  LLM02 Sensitive Info:          PASS / FAIL
  LLM03 Supply Chain:            PASS / FAIL
  LLM04 Data/Model Poisoning:    PASS / FAIL
  LLM05 Output Handling:         PASS / FAIL
  LLM06 Excessive Agency:        PASS / FAIL
  LLM07 System Prompt:           PASS / FAIL
  LLM08 Vector/Embedding:        PASS / FAIL
  LLM09 Misinformation:          PASS / FAIL
  LLM10 Unbounded Consumption:   PASS / FAIL

PLOT4ai diagram: designs/TMD/<service>.yaml [UPDATED / CREATED]
  Open threats: <N> (<severities>)
  New threats:  <list>
```
