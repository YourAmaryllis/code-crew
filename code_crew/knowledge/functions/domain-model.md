---
name: SDLC-Architect-DomainModel
description: The project's concrete domain model — bounded contexts, aggregates, entities, value objects, and ubiquitous language. Owned by the architect.
metadata:
  type: process
  role: architect
  phase: "3, 5"
---

# Domain Model

The domain model captures the core business concepts, their relationships, and the shared vocabulary between business and engineering. It is **owned by the architect**, who authors and maintains it. The Product Owner provides business vocabulary and validates that domain terms match business reality; the architect decides the technical structure (bounded contexts, aggregates, entities).

---

## Domain-Driven Design (DDD) Approach

The domain model uses DDD concepts:

| Concept | Definition |
|---------|-----------|
| **Bounded Context** | A named, scoped part of the domain with its own model and language |
| **Aggregate** | A cluster of entities treated as one unit for data changes |
| **Entity** | An object with identity (e.g. User, Dataset, CurationRequest) |
| **Value Object** | An immutable object defined by its attributes (e.g. Email, DatasetHash) |
| **Domain Event** | Something that happened in the domain (e.g. DatasetSubmitted, CurationCompleted) |
| **Repository** | Interface for retrieving and storing aggregates |
| **Domain Service** | Logic that doesn't naturally belong to a single entity |

---

## Bounded Contexts

Each bounded context maps (roughly) to a backend service. Cross-context interactions go through events or explicit API calls — never shared database tables.

Current contexts (update as the product evolves):

| Context | Core Concepts | Service |
|---------|--------------|---------|
| Identity | User, Organization, Role, Permission | `auth-svc` |
| Data Curation | CurationRequest, Dataset, DeIdentificationJob | `curation-svc` |
| Billing | Subscription, Invoice, PaymentMethod | `billing-svc` |
| Notifications | Notification, Channel, Template | `notification-svc` |
| Portal | (React SPA consuming all contexts via API) | `portal` |

---

## Domain Model Format

Document the domain model for each bounded context as a Markdown file in `designs/PLAN/` or as part of the relevant ADD.

```markdown
## Bounded Context: Data Curation

### Aggregates

#### CurationRequest (aggregate root)
- id: UUID
- status: draft | submitted | processing | completed | failed
- submittedBy: UserId (reference to Identity context)
- dataset: Dataset (owned entity)
- deIdentificationJob: DeIdentificationJob (owned entity)
- createdAt: Timestamp
- completedAt: Timestamp?

#### Dataset (entity, owned by CurationRequest)
- id: UUID
- storageRef: S3ObjectReference (value object)
- sizeBytes: int
- checksum: SHA256Hash (value object)
- custodyLog: CustodyLogEntry[] (value objects)

### Value Objects
- S3ObjectReference: { bucket: string, key: string, region: string }
- SHA256Hash: string (validated format)
- CustodyLogEntry: { at: Timestamp, actor: UserId, action: string }

### Domain Events
- CurationRequestSubmitted { requestId, submittedBy, submittedAt }
- DeIdentificationCompleted { requestId, outputDataset, completedAt }
- CurationRequestFailed { requestId, reason, failedAt }

### Repository Interfaces
- CurationRequestRepository: GetByID, Save, ListByUser
```

---

## Ubiquitous Language

The domain model defines the shared language between product and engineering. When a business person says "curation request," the code also says `CurationRequest` — not `Job`, `Task`, or `Item`.

Document the ubiquitous language glossary in the relevant BRD or domain model file:

```markdown
## Glossary

| Term | Definition |
|------|-----------|
| Curation Request | A request to de-identify and process a customer dataset |
| De-identification | The process of removing PHI per HIPAA Safe Harbor |
| Custody Log | An immutable record of who handled the dataset and when |
```

---

## Relationship to SAD and ADDs

- The SAD includes a high-level context map (which bounded contexts exist and how they relate)
- ADDs describe the detailed design within a bounded context
- When a new bounded context is added, update the SAD and write an ADD

See: `sad-maintenance`

---

## Maintaining the Domain Model

Update the domain model when:
- A new entity or aggregate is introduced
- An existing aggregate's boundaries change (e.g. extracting an entity into its own aggregate)
- Ubiquitous language changes (rename by updating both the model and the code)

The architect reviews domain model changes — language shifts affect every layer of the system.

---

## AI Assistance

AI can generate draft domain models from:
- BRD content
- User journey maps
- Existing codebase analysis

Prompt pattern:
```
Given this business requirements document and user journey, identify the bounded contexts,
key aggregates, entities, and value objects for the data curation domain. Use DDD vocabulary.
Output as a Markdown table.
```

Human architect and product owner review and refine.
