---
name: Function-DomainDrivenDesign
description: Domain-Driven Design principles — bounded contexts, aggregates, ubiquitous language, and how they map to code structure
metadata:
  type: function
  roles: [architect, product-owner, engineer]
  phase: "3, 5, 17, 18"
---

# Domain-Driven Design (DDD)

DDD aligns the software model with the business domain. The architect and Product Owner co-create the domain model; engineers implement it following the patterns defined here.

---

## Core Concepts

| Concept | Definition | Code Mapping |
|---------|-----------|-------------|
| **Bounded Context** | A named scope with its own model and language | One service (or module) per context |
| **Aggregate** | A cluster of entities treated as one unit for changes | Single repository interface; one DB transaction |
| **Aggregate Root** | The entry point into an aggregate — only it is referenced from outside | Exported type in `domain/` package |
| **Entity** | Has identity that persists across state changes | Struct with an `ID` field |
| **Value Object** | Immutable; defined by its attributes, not identity | Struct with no ID; validated on construction |
| **Domain Event** | Something that happened; communicates state change across contexts | Published to event bus; named in past tense |
| **Repository** | Interface for loading/saving aggregates | Defined in `domain/`, implemented in `repo/` |
| **Domain Service** | Logic that doesn't belong to one entity | Stateless function in `domain/` |
| **Anti-Corruption Layer** | Translation between bounded contexts or external APIs | Adapter in `repo/` or separate `adapter/` package |

---

## Ubiquitous Language

The domain model defines a shared vocabulary. The same terms used in:
- Business requirements (BRD)
- User stories (Jira)
- Code (type names, function names, variable names)
- Tests (BDD scenario names)

When business language shifts, code must shift too — tracked via ADR if the change is significant.

**Rule**: never let technical jargon bleed into domain code. A `User` is a `User`, not a `UserRecord`, `UserDTO`, or `UserEntity`.

---

## Bounded Context Design

Each bounded context:
- Has its own data store (no shared tables between contexts)
- Communicates with other contexts via **domain events** or **explicit API calls**
- Has its own ubiquitous language (the same word may mean different things in different contexts)

Context map:
```
[Identity Context] ──owns──► User, Organization
[Billing Context]  ──references──► UserId (from Identity, no join)
[Orders Context]   ──subscribes──► UserRegistered event (from Identity)
```

Identify context boundaries by asking: "Where does this concept mean something different?"

---

## Aggregate Design Rules

1. One aggregate per repository transaction — don't span aggregates in one DB write
2. Reference other aggregates by ID only — never hold a direct object reference
3. Keep aggregates small — if it grows beyond ~7 fields, consider decomposition
4. Invariants (business rules) are enforced inside the aggregate — never outside

```go
// Good: invariant enforced inside
func (o *Order) AddItem(item Item) error {
    if o.status != StatusDraft {
        return ErrOrderNotEditable
    }
    o.items = append(o.items, item)
    return nil
}

// Bad: invariant leaking to application layer
if order.Status == "draft" {
    order.Items = append(order.Items, item) // direct mutation
}
```

---

## Value Objects

Value objects carry meaning and validate themselves on construction:

```go
type Email struct{ value string }

func NewEmail(s string) (Email, error) {
    if !strings.Contains(s, "@") {
        return Email{}, errors.New("invalid email format")
    }
    return Email{value: strings.ToLower(s)}, nil
}

func (e Email) String() string { return e.value }
```

Never expose raw primitives for domain-meaningful concepts. An `Email` is not a `string`.

---

## Domain Events

Events communicate between bounded contexts without tight coupling:

```go
type UserRegistered struct {
    UserID    string
    Email     Email
    OccurredAt time.Time
}
```

Rules:
- Named in past tense (`UserRegistered`, not `RegisterUser`)
- Immutable — never mutate an event after creation
- Consumers process events eventually — do not rely on synchronous handling
- Events cross context boundaries; commands stay within one context

---

## Directory Structure (per stack)

The code layout for DDD patterns varies by stack. Read the relevant stack document for specifics:
- Go: `stacks/go-backend` → `internal/domain/`, `internal/usecase/`, `internal/repo/`
- TypeScript: `stacks/typescript-react` → domain layer in shared lib
- Python: `stacks/python` → `src/<context>/domain/`, `src/<context>/application/`

---

## DDD and the Domain Model Document

The `domain-model` function document describes the domain model for your specific project. This document (`domain-driven-design`) provides the methodology. Use this as the reference when authoring or reviewing domain-model.md.
