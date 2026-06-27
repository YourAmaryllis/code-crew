---
name: SDLC-Security-ThreatModel
description: OpenThreatModel (OTM) YAML format, framework selection (STRIDE/LINDDUN/CIA/DIE/PLOT4ai), threat model maintenance, and where to store model files
metadata:
  type: process
  role: security-lead
  tool: open-threat-model
  reference: https://github.com/iriusrisk/OpenThreatModel
---

# OpenThreatModel — Threat Model Maintenance

Threat models are stored as OpenThreatModel (OTM) YAML files (v0.2.0) and committed to version control under `designs/TMD/`. They are the authoritative record of trust zones, components, data flows, and threats per service.

---

## File Storage

```
designs/TMD/<service-name>.yaml
```

One file per logical service or component. Naming uses the same slug as the service in the SAD (e.g. `api-gateway.yaml`, `data-pipeline.yaml`, `portal.yaml`).

Run `/explore` in the REPL to auto-generate a starter OTM file with detected components.

---

## Choosing a Framework

A single OTM file covers all frameworks — the `categories` array on each threat identifies which framework it belongs to.

| Framework | When to use | Example categories |
|-----------|------------|-------------------|
| **STRIDE** | Default for APIs, services, data stores, auth flows | `Spoofing`, `Tampering`, `Repudiation`, `Information Disclosure`, `Denial of Service`, `Elevation of Privilege` |
| **PLOT4ai** | Any component containing an LLM, ML model, embedding store, RAG pipeline, or inference endpoint | `Output Control`, `Privacy Violation`, `Security Breach`, `Fairness`, `Accountability` |
| **LINDDUN** | Personal-data flows when GDPR or CCPA stacks are active | `Linking`, `Identifying`, `Data Disclosure`, `Unawareness`, `Non-compliance` |
| **CIA** | Executive risk summaries, compliance control mapping — too coarse for code review | `Confidentiality`, `Integrity`, `Availability` |

**Why PLOT4ai over STRIDE for AI?** STRIDE has no concept for prompt injection, training data poisoning, model extraction, membership inference, adversarial inputs, hallucination harm, or bias. PLOT4ai covers all of these. Use both in the same file: STRIDE threats on the API/infrastructure components, PLOT4ai threats on the AI processing components.

---

## When to Create or Update

**Create** when: new service, new external integration, new data store, new AI/ML component.

**Update** when: new API endpoint, auth logic changes, new trust boundary, threat mitigated, new threat found in review, LLM prompt template changes.

**No update needed** for: bug fix without architectural change, UI styling, performance optimisation with no new data paths.

---

## OTM YAML Structure

```yaml
otmVersion: 0.2.0

project:
  name: Service Name
  id: service-name
  description: One-paragraph description of what this service does and what it protects
  owner: Security Lead

representations:
  - name: Architecture Diagram
    id: arch-diagram
    type: diagram

assets:
  - name: User PII
    id: user-pii
    description: Name, email, address — personal data subject to GDPR
    risk:
      confidentiality: 3
      integrity: 2
      availability: 1

components:
  - name: External User
    id: external-user
    description: Authenticated portal user
    parent:
      trustZone: internet
    type: actor

  - name: API Service
    id: api-service
    description: Handles authentication and business logic
    parent:
      trustZone: private
    type: service
    assets:
      processed:
        - user-pii
      stored: []

  - name: PostgreSQL
    id: postgres
    description: Stores user records and application state — encrypted at rest
    parent:
      trustZone: data
    type: datastore
    assets:
      stored:
        - user-pii

trustZones:
  - name: Internet
    id: internet
    description: Public internet — untrusted
    risk:
      trustRating: 0

  - name: Private
    id: private
    description: Internal VPC — restricted access
    risk:
      trustRating: 75

  - name: Data
    id: data
    description: Persistent storage layer — encrypted at rest, private network only
    risk:
      trustRating: 80

dataflows:
  - name: HTTPS API Request
    id: df-user-api
    description: Authenticated API call carrying JWT
    bidirectional: false
    source: external-user
    destination: api-service
    assets:
      - user-pii
    attributes:
      protocol: HTTPS
      isEncrypted: true
      isPublicNetwork: true

threats:
  - name: JWT forgery — impersonate another user
    id: threat-001
    categories:
      - Spoofing
    risk:
      likelihood: HIGH
      impact: HIGH
    description: >
      An attacker could forge a JWT by exploiting weak key management or
      algorithm confusion (RS256 → HS256) to impersonate another user.
    mitigations:
      - mitigation-001

  - name: Prompt injection via user-controlled input
    id: threat-002
    categories:
      - Output Control
    risk:
      likelihood: HIGH
      impact: MEDIUM
    description: >
      An attacker injects malicious instructions into an LLM prompt through
      user-controlled content, causing the model to bypass system instructions
      or exfiltrate data from context.
    mitigations:
      - mitigation-002

mitigations:
  - name: JWT validation using JWKS public key
    id: mitigation-001
    description: >
      Validate JWT signature on every request using the public key from the
      JWKS endpoint. Enforce expiry. Reject RS256/HS256 algorithm switching.
    riskReduction: 85
    status: implemented

  - name: Input sanitization and prompt hardening
    id: mitigation-002
    description: >
      Sanitize user input before inclusion in prompts. Keep user content clearly
      delimited from system instructions. Use system-prompt-level instructions
      that the user message cannot override.
    riskReduction: 70
    status: implemented
```

---

## STRIDE Threat Categories

| Category | What it models |
|----------|---------------|
| `Spoofing` | Impersonating a user, service, or component |
| `Tampering` | Modifying data in transit or at rest without authorisation |
| `Repudiation` | Denying an action was taken; insufficient audit trail |
| `Information Disclosure` | Exposing data to unauthorised parties |
| `Denial of Service` | Making a service unavailable |
| `Elevation of Privilege` | Gaining more permissions than granted |

---

## PLOT4ai Threat Categories

| Category | What it models | Key examples |
|----------|---------------|-------------|
| `Privacy Violation` | Exposing personal data through model behaviour | Membership inference, model inversion, PII logged from prompt/completion |
| `Linkability` | Re-identifying individuals from outputs or embeddings | Embedding similarity reveals identity; output fingerprinting |
| `Output Control` | Harmful, wrong, or manipulated model outputs | Prompt injection, jailbreak, hallucination causing real harm |
| `Transparency` | Lack of explainability or disclosure | Undisclosed training data, unexplainable decisions, hidden model version |
| `Security Breach` | Attacks on model integrity or confidentiality | Adversarial inputs, training data poisoning, model extraction/theft |
| `Availability` | Model degradation or resource exhaustion | DoS via adversarial inputs, excessive token consumption |
| `Fairness` | Biased or discriminatory outputs | Demographic parity failures, amplified dataset bias |
| `Accountability` | No audit trail or governance on model decisions | Unversioned models, no rollback, no decision audit log |

---

## LINDDUN Threat Categories (when GDPR/CCPA active)

| Category | What it models |
|----------|---------------|
| `Linking` | Combining data items to infer more than intended |
| `Identifying` | Identifying an individual from data that shouldn't allow it |
| `Non-repudiation` | User unable to deny an action (privacy violation) |
| `Detecting` | Inferring that an individual is a system user |
| `Data Disclosure` | Exposing personal data to unintended parties |
| `Unawareness` | User unaware of processing or unable to exercise rights |
| `Non-compliance` | Failing to meet regulatory obligations (GDPR/CCPA) |

---

## Minimum Threat Coverage per Component Type

### Traditional components (STRIDE)

| Component | Required coverage |
|-----------|------------------|
| Public API endpoint | Spoofing (auth bypass), Tampering (input), Information Disclosure (over-fetching), Denial of Service (rate limit) |
| Internal service | Tampering (data integrity), Elevation of Privilege (lateral movement) |
| Data store | Tampering (unauthorised write), Information Disclosure (data leak), Repudiation (audit trail) |
| Auth flow | Spoofing (credential theft), Repudiation (session forgery) |
| Data flow crossing boundary | Tampering (MITM), Information Disclosure (plaintext) |

### AI/ML components (PLOT4ai)

| Component | Required coverage |
|-----------|-----------------|
| LLM / inference endpoint | Output Control (prompt injection), Security Breach (model extraction), Privacy Violation (PII in prompt), Accountability (decision audit trail) |
| Embedding store | Privacy Violation (membership inference), Linkability (re-identification), Security Breach (embedding poisoning) |
| Training / fine-tuning pipeline | Security Breach (data poisoning), Fairness (dataset bias), Accountability (model version tracking) |
| RAG retriever | Output Control (context injection via retrieved docs), Security Breach (retrieval manipulation), Transparency (undisclosed sources) |
| Agent / tool-calling system | Output Control (unsafe tool invocation), Accountability (tool call audit trail), Availability (runaway tool loops) |
| Model registry / artifact store | Security Breach (supply chain compromise), Accountability (unsigned artifacts), Availability (model deletion) |

---

## IriusRisk Import

OTM YAML files can be imported directly into IriusRisk for risk management, control mapping, and compliance reporting.

### Via StartLeft CLI (recommended)

[StartLeft](https://github.com/iriusrisk/startleft) is IriusRisk's open-source OTM conversion tool:

```bash
# Install
pip install startleft

# Validate the OTM file before import
startleft validate otm designs/TMD/<service>.yaml

# Convert OTM → IriusRisk native format (for manual upload)
startleft parse \
  --type OTM \
  --output-type IRIUSRISK \
  --output-file /tmp/<service>-iriusrisk.xml \
  designs/TMD/<service>.yaml

# Or import directly to IriusRisk via API
startleft export \
  --type OTM \
  --iriusrisk-url https://<instance>.iriusrisk.com \
  --api-token <TOKEN> \
  designs/TMD/<service>.yaml
```

### Via IriusRisk REST API

```bash
curl -X POST "https://<instance>.iriusrisk.com/api/v1/threats/import" \
  -H "Content-Type: application/yaml" \
  -H "api-token: <TOKEN>" \
  --data-binary @designs/TMD/<service>.yaml
```

IriusRisk maps OTM `categories` to its threat library automatically. STRIDE and PLOT4ai categories are both recognized. Controls in `mitigations` are imported as countermeasures.

---

## Security Lead Review Steps

1. Load `jira_view` to understand the feature scope
2. Check `designs/TMD/` for an existing model for the affected service (`workspace_reader`)
3. Determine which frameworks apply:
   - Always: STRIDE for traditional API/store/boundary components
   - If AI/ML components present or `ai-ml` stack active: also PLOT4ai threats
   - If personal data in scope and GDPR/CCPA stack active: also LINDDUN threats
4. If a model exists: update components, dataflows, and threats for new surface area; update mitigation `status` for resolved items
5. If no model exists: create a new OTM YAML file covering all components, trust zones, data flows, and threats
6. Write the updated/new file to `designs/TMD/<service>.yaml` via `platform_shell`
7. Produce the output summary (see format below)

---

## Output Summary Format

```
THREAT MODEL: designs/TMD/<service>.yaml [UPDATED / CREATED]

Frameworks: STRIDE [+ PLOT4ai] [+ LINDDUN]
Components: <list of components by type>
Trust zones: internet / private / data
Data flows: <count> total, <count> cross-boundary

Open threats (STRIDE):     <N> — <High/Critical count>
Open threats (PLOT4ai):    <N> — <High/Critical count>   ← omit if no AI components
Open threats (LINDDUN):    <N>                           ← omit if no PII scope

New threats added this review:
  - [HIGH] Spoofing: <title> — <one-line description>
  - [CRITICAL] Output Control: <title> — <one-line description>
```
