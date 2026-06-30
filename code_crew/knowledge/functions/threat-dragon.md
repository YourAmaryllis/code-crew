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

## Threat Modeling Manifesto Principles

The Threat Modeling Manifesto (https://www.threatmodelingmanifesto.org/) defines the values that make threat modeling effective:

**Core values (prefer the left over the right):**
- People and collaboration **over** processes and tools
- A culture of finding and fixing design issues **over** checking compliance boxes
- A journey of understanding **over** a security snapshot
- Doing threat modeling **over** talking about it

**Key principles:**
- The best threat modelers are collaborative, systematic, and curious — not just checklist-followers
- Threat modeling should be done early, iteratively, and continuously as the system evolves
- The output that matters is an improved security posture, not a document for its own sake
- Ask: What are we building? What can go wrong? What are we going to do about it? Did we do a good enough job?

---

Threat models are stored as OpenThreatModel (OTM) YAML files (v0.2.0) and committed to version control under `designs/TMD/`. They are the authoritative record of trust zones, components, data flows, and threats per service.

## Tool Format Reference (what other tools use — we still use OTM)

| Tool | File format | Relation to OTM |
|------|------------|----------------|
| **OTM (ours)** | YAML (primary) or JSON (schema: https://github.com/iriusrisk/OpenThreatModel) | Authoritative format |
| **OWASP Threat Dragon** | JSON — own schema (`version`, `summary`, `detail.diagrams[]`) | **Not OTM** — different format entirely |
| **IriusRisk export** | XML — proprietary draw.io-based format (`<project>`, `<diagram><schema>` base64) | **Not OTM** — their own format |
| **IriusRisk import** | OTM YAML via StartLeft CLI (`startleft parse --type OTM`) | Can consume OTM |

Use **StartLeft CLI** (`pip install startleft`) to convert OTM YAML → IriusRisk if needed. IriusRisk's XML export cannot be imported directly as OTM and is not compatible.

---

## File Storage

```
designs/TMD/<service-name>.yaml
```

One file per logical service or component. Naming uses the same slug as the service in the SAD (e.g. `api-gateway.yaml`, `data-pipeline.yaml`, `portal.yaml`).

Run `/explore` in the REPL to auto-generate a starter OTM file with detected components.

---

## Choosing a Framework

A single OTM file covers all applicable frameworks — the `categories` array on each threat identifies which framework it belongs to. Apply the right framework per component based on its nature.

| Framework | When to use | Key categories |
|-----------|------------|----------------|
| **STRIDE** | Always — all APIs, services, data stores, auth flows, network boundaries | `Spoofing`, `Tampering`, `Repudiation`, `Information Disclosure`, `Denial of Service`, `Elevation of Privilege` |
| **PLOT4ai** | Any AI/ML component: LLM inference, embedding store, RAG pipeline, data curation pipeline, training workflow, recommendation engine | `Output Control`, `Privacy Violation`, `Linkability`, `Security Breach`, `Fairness`, `Accountability`, `Transparency`, `Availability` |
| **LINDDUN** | Personal data (PII/PHI) flows when GDPR, CCPA, or HIPAA stacks are active | `Linking`, `Identifying`, `Non-repudiation`, `Detecting`, `Data Disclosure`, `Unawareness`, `Non-compliance` |
| **CIA** | Risk asset classification (applied to every `asset` in the OTM as `risk.confidentiality/integrity/availability` ratings) — not a separate threat pass but a risk lens on all threats | `Confidentiality`, `Integrity`, `Availability` |
| **DIE** | Cloud-native services deployed in ECS/Lambda/Kubernetes — evaluate resilience against compromise | `Distributed` (blast radius isolation), `Immutable` (artifact integrity, no in-place mutation), `Ephemeral` (credential lifetime, container lifespan, session duration) |

**Framework selection by system type:**

| System type | Primary | Add |
|-------------|---------|-----|
| Traditional REST API | STRIDE | LINDDUN if PII/PHI |
| Data store / database | STRIDE | LINDDUN if personal data; CIA ratings on all assets |
| LLM / inference endpoint | STRIDE (infrastructure) + PLOT4ai (model) | LINDDUN if user PII in prompts |
| Data curation / training pipeline | STRIDE + PLOT4ai (data poisoning, bias, provenance) | LINDDUN if training data includes personal data |
| Container attestation / supply chain | STRIDE + PLOT4ai (supply-chain AI) + DIE (immutable artifacts) | — |
| Cloud-native microservice (ECS/Lambda) | STRIDE + DIE | LINDDUN if PII; PLOT4ai if AI |
| Auth service / IAM | STRIDE | LINDDUN (user tracking, consent) |

**Why PLOT4ai over STRIDE for AI?** STRIDE has no concept for prompt injection, training data poisoning, model extraction, membership inference, adversarial inputs, hallucination harm, or bias. PLOT4ai covers all of these. Apply STRIDE on the infrastructure/API layer and PLOT4ai on the AI processing components — both in the same OTM file.

**Why DIE for cloud-native?** DIE shifts the question from "can we prevent compromise?" to "how fast can we recover and how limited is the blast radius?" Distributed: can one compromised instance affect others? Immutable: are deployed artifacts signed and unmodifiable? Ephemeral: do credentials and sessions expire quickly enough to limit dwell time?

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

## LINDDUN Threat Categories (when GDPR/CCPA/HIPAA active)

LINDDUN focuses on privacy threats — use it when personal data (PII/PHI) flows through the system.

| Category | What it models |
|----------|---------------|
| `Linking` | Combining data items to infer more than intended (e.g. correlating session data + health queries to identify a person) |
| `Identifying` | Identifying an individual from data that shouldn't allow it (e.g. quasi-identifiers in aggregate queries) |
| `Non-repudiation` | Permanent attribution of an action to a user — a privacy violation when the user has no way to dispute or have it erased |
| `Detecting` | Inferring that an individual uses the system at all (e.g. presence detection from traffic patterns) |
| `Data Disclosure` | Exposing personal data to unintended parties (e.g. overly broad API responses, log leakage) |
| `Unawareness` | User unaware of how their data is processed or unable to exercise rights (right to access, erasure, portability) |
| `Non-compliance` | Failing to meet regulatory obligations (GDPR Art.5/6/17, CCPA, HIPAA §164.312) |

---

## DIE Threat Categories (cloud-native / distributed services)

DIE (Distributed, Immutable, Ephemeral) is a resilience-oriented framework — not "can we prevent compromise?" but "how limited is the blast radius and how fast can we recover?"

| Category | What it models | Example threats |
|----------|---------------|----------------|
| `Distributed` | Blast radius from a single compromised instance | Can one compromised ECS task affect other tenants? Is tenant isolation enforced at the network layer? |
| `Immutable` | Integrity of deployed artifacts — no in-place mutation | Are container images signed and verified at deploy time? Can a running container write to its own filesystem? Is the OTM itself version-controlled and tamper-evident? |
| `Ephemeral` | Short-lived credentials, sessions, and workloads reduce dwell time | Are IAM role credentials valid for minutes (task role) or hours (long-lived key)? Are DB sessions closed after use? Are containers restarted on a schedule? |

**When to apply DIE:** any component deployed as a container, Lambda, or ECS task. Also apply to the container attestation service — it is itself a DIE system (pipeline produces signed, immutable artifacts; attestation results are ephemeral per build).

---

## CIA Risk Lens (applied to assets, not a separate threat pass)

CIA (Confidentiality, Integrity, Availability) is used as a risk classification for OTM `assets`, not enumerated as separate threats. Every asset must have ratings:

```yaml
assets:
  - name: PHI Clinical Record
    id: phi-clinical
    risk:
      confidentiality: HIGH   # Breach causes HIPAA violation + patient harm
      integrity: HIGH         # Incorrect record causes clinical error
      availability: MEDIUM    # Short outage tolerable; prolonged outage causes care delay
```

Use CIA ratings to:
- Prioritise STRIDE/PLOT4ai/LINDDUN threats (HIGH CIA assets → HIGH threat severity)
- Map to HIPAA, SOC 2, and GDPR control requirements in the compliance scan
- Determine minimum mitigation coverage (HIGH/HIGH/HIGH assets need implemented mitigations, not just planned)

---

## Minimum Threat Coverage per Component Type

### Traditional components (STRIDE)

| Component | Required coverage |
|-----------|------------------|
| Public API endpoint | Spoofing (auth bypass), Tampering (input), Information Disclosure (over-fetching), Denial of Service (rate limit) |
| Internal service | Tampering (data integrity), Elevation of Privilege (lateral movement) |
| Data store | Tampering (unauthorised write), Information Disclosure (data leak), Repudiation (audit trail) |
| Auth flow | Spoofing (credential theft), Repudiation (session forgery) |
| Data flow crossing trust boundary | Tampering (MITM), Information Disclosure (plaintext) |

### Cloud-native / containerised services (DIE — add alongside STRIDE)

| Component | Required coverage |
|-----------|------------------|
| ECS task / Lambda function | Distributed (tenant isolation, blast radius), Immutable (image signing + read-only filesystem), Ephemeral (task role credential TTL, no long-lived keys) |
| Container image pipeline | Immutable (signed image digest, provenance attestation), Distributed (registry isolation per environment) |
| Service mesh / sidecar | Ephemeral (mTLS certificate rotation period), Distributed (per-service network policy) |

### AI/ML components (PLOT4ai — add alongside STRIDE)

| Component | Required coverage |
|-----------|-----------------|
| LLM / inference endpoint | Output Control (prompt injection), Security Breach (model extraction), Privacy Violation (PII in prompt), Accountability (decision audit trail) |
| Embedding store | Privacy Violation (membership inference), Linkability (re-identification), Security Breach (embedding poisoning) |
| Data curation / training pipeline | Security Breach (data poisoning), Fairness (dataset bias), Accountability (model version + data lineage tracking) |
| Data guide / recommendation engine | Output Control (hallucination causing downstream harm), Privacy Violation (user query PII leakage), Transparency (unexplained recommendations) |
| RAG retriever | Output Control (context injection via retrieved docs), Security Breach (retrieval manipulation), Transparency (undisclosed sources) |
| Agent / tool-calling system | Output Control (unsafe tool invocation), Accountability (tool call audit trail), Availability (runaway tool loops) |
| Model registry / artifact store | Security Breach (supply chain compromise), Accountability (unsigned artifacts), Availability (model deletion) |
| Container attestation service | Security Breach (supply chain AI — forged attestation), Immutable (attestation result integrity), Accountability (attestation audit log) |

### Personal-data components (LINDDUN — add when PII/PHI in scope)

| Component | Required coverage |
|-----------|------------------|
| User profile / identity store | Identifying (re-identification from profile fields), Data Disclosure (over-broad API response), Unawareness (no consent management UI) |
| Health data processor | Linking (correlation of health + identity data), Non-compliance (HIPAA retention + access control), Unawareness (patient rights — access, erasure, portability) |
| Analytics / audit log | Detecting (user presence inference), Linking (cross-session correlation), Non-compliance (log retention beyond legal minimum) |

---

## Tool Format Details (CLI and integration)

### OTM (OpenThreatModel) — primary format

OTM is the authoritative format for all threat models in this project. Maintained as YAML in `designs/TMD/`.
- Spec: https://github.com/iriusrisk/OpenThreatModel
- OTM supports both YAML and JSON outputs (JSON schema is in the OTM repo)
- We use YAML for readability and diff-friendliness in code review

### OWASP Threat Dragon — visualisation tool

Threat Dragon (https://owasp.org/www-project-threat-dragon/) uses its **own JSON format**, not OTM:
- Root keys: `version`, `summary`, `detail` (with `diagrams` array)
- Each diagram has `cells` array: `type: "tm.Process"`, `"tm.Store"`, `"tm.Actor"`, `"tm.Boundary"`, `"tm.Flow"`
- Threat Dragon v2 can **export to OTM format** — use this when moving models into `designs/TMD/`
- Do **not** store Threat Dragon JSON in `designs/TMD/` — convert to OTM first

### IriusRisk — risk management platform

IriusRisk (https://www.iriusrisk.com/) uses a **proprietary XML format**, completely different from OTM:
- Root element: `<project ref="..." name="..." workflowState="Draft">`
- Contains `<diagram>` with base64-encoded draw.io schema, `<trustZones>`, `<usecases>`, `<components>` subtrees
- Uses IriusRisk-specific attributes: `ir.type=TRUSTZONE`, `ir.type=COMPONENT`, `ir.ref=<uuid>`
- `designs/TMD/LooporaData.xml` is an IriusRisk export — it is **not** OTM and cannot be validated as OTM

**To import OTM → IriusRisk** use [StartLeft](https://github.com/iriusrisk/startleft), IriusRisk's open-source conversion CLI:

```bash
pip install startleft

# Validate the OTM file
startleft validate otm designs/TMD/<service>.yaml

# Convert OTM → IriusRisk XML (for manual upload)
startleft parse \
  --type OTM \
  --output-type IRIUSRISK \
  --output-file /tmp/<service>-iriusrisk.xml \
  designs/TMD/<service>.yaml
```

IriusRisk maps OTM `categories` to its threat library. STRIDE and PLOT4ai categories are both recognized. Controls in `mitigations` are imported as countermeasures.

---

## Security Lead Review Steps

1. Load `jira_view` to understand the feature scope
2. Check `designs/TMD/` for an existing model for the affected service (`workspace_reader`)
3. Determine which frameworks apply (see "Choosing a Framework" table above):
   - **STRIDE**: always, for all API/service/data-store/boundary components
   - **PLOT4ai**: if `ai-ml` stack active, or component is a data curation pipeline, data guide/recommendation engine, container attestation service, LLM endpoint, embedding store, RAG retriever, or agent system
   - **LINDDUN**: if personal data (PII/PHI) is in scope and GDPR, CCPA, or HIPAA stacks are active
   - **DIE**: if component is deployed as ECS task, Lambda, or container — check Distributed, Immutable, Ephemeral
   - **CIA**: always — rate every asset `confidentiality/integrity/availability` in the OTM
4. If a model exists: update components, dataflows, and threats for new surface area; update mitigation `status` for resolved items
5. If no model exists: create a new OTM YAML file covering all components, trust zones, data flows, and threats
6. Write the updated/new file to `designs/TMD/<service>.yaml` via `platform_shell`
7. Produce the output summary (see format below)

---

## Output Summary Format

```
THREAT MODEL: designs/TMD/<service>.yaml [UPDATED / CREATED]

Frameworks: STRIDE [+ PLOT4ai] [+ LINDDUN] [+ DIE]
Components: <list of components by type>
Trust zones: internet / private / data
Data flows: <count> total, <count> cross-boundary

Open threats (STRIDE):     <N> — <High/Critical count>
Open threats (PLOT4ai):    <N> — <High/Critical count>   ← omit if no AI components
Open threats (LINDDUN):    <N>                           ← omit if no PII scope
Open threats (DIE):        <N>                           ← omit if not cloud-native

New threats added this review:
  - [HIGH] Spoofing: <title> — <one-line description>
  - [CRITICAL] Output Control: <title> — <one-line description>
  - [HIGH] Immutable: <title> — unsigned artifact deployed without verification
```
