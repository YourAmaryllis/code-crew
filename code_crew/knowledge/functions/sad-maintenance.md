---
name: SDLC-Architect-SADMaintenance
description: What the SAD is, its structure, when to update it, and the relationship between SAD updates and ADRs/ADDs
metadata:
  type: process
  role: architect
  phase: "5, 8, 11, 19"
---

# Solution Architecture Document (SAD)

The SAD is the overarching architecture document that covers the **entire application**. It is the **ultimate source of truth** for how the system is structured, how components connect, and how data flows. When the SAD disagrees with the code, the SAD is wrong and must be updated — not the code.

ADRs and ADDs are subordinate to the SAD:

- An **ADR** records the decision that changed the SAD
- An **ADD** expands on a specific component or module in the SAD with implementation detail

See `architecture-decisions` for ADR and ADD formats and when to write them.

---

## SAD Structure

The SAD is split into sections, one file per view. This makes review and editing tractable and lets sections evolve independently.

| Section | Content |
|---------|---------|
| **1 — Introduction** | Purpose, quality goals, architecture presentation, value proposition |
| **2 — System Overview** | Technology choices, compliance posture, overall architecture, key domain models and user journeys |
| **3 — Decomposition View** | Services and components: responsibilities, interfaces, dependencies |
| **4 — Network View** | VPCs, subnets, security groups, ingress/egress per flow |
| **5 — Data Flow View** | How data moves: sources, sinks, transformations, encryption in transit |
| **6 — Deployment View** | Environments (dev / staging / prod), ECS services, Terraform layout, CI/CD |
| **7 — Security View** | Auth, IAM, secrets management, trust boundaries, compliance controls per flow |
| **8 — Additional Considerations** | Cross-cutting: zero-custody, E2EE, consent, geolocation, cost, operations, scalability |

### Subsection pattern for views 3–7

Every architecture view (Decomposition, Network, Data Flow, Deployment, Security) follows the same internal structure. This makes it easy to find "how does the rental request flow work from a security perspective" — it's always section 7.4.

```
X.1  Context          — what this view shows and what questions it answers
X.2  Overview         — high-level diagram of the full system in this view
X.3  [Flow A]         — the primary user-facing flow traced through this view
X.4  [Flow B]         — second major flow
X.5  [Flow C]         — third major flow
X.6  [Flow D]         — fourth major flow
X.7  Supporting [X]   — auxiliary flows, background processes, edge cases
X.8  Related Documents — ADRs, ADDs, and other SAD sections that this view depends on
```

When writing or updating a view, cover **all key flows** from the same angle — don't describe the deployment topology for registration but skip it for the usage flow. Consistency is what makes the views navigable.

---

## Relationship to ADRs

**Almost every SAD update requires a new ADR.** The ADR captures the decision; the SAD reflects the outcome.

| Trigger | Action |
|---------|--------|
| Introducing a new service | New ADR + update Decomposition View and Deployment View |
| Changing the auth mechanism | New ADR + update Security View |
| Switching data stores | New ADR + update Data Flow View and Decomposition View |
| Deprecating a service | New ADR (superseding the original adoption ADR) + update relevant SAD sections |
| Adding a major third-party integration | New ADR + update System Overview and Data Flow View |

Exception: purely structural SAD edits (fixing a diagram, correcting a typo, adding a missing label) do not need an ADR.

---

## Relationship to ADDs

ADDs are not part of the SAD — they expand on it. When the SAD says "the attestation service validates image checksums," the ADD (e.g. ADD-016) describes *how*: the checksum manifest format, the challenge/response protocol, the CA that issues certs.

A component that appears in the SAD's Decomposition View should have a corresponding ADD if its implementation is non-trivial. The SAD references the ADD; the ADD references the SAD section it expands.

---

## When to Update the SAD

**Update the SAD when:**

- A new service or component is introduced
- A service is deprecated or removed
- A significant integration is added (new third-party API, event bus, data store)
- An ADR changes a cross-cutting decision (deployment model, auth, data residency)
- The data flow between major components changes
- A security boundary is added, removed, or moved

**Do not update the SAD for:**

- Implementation details within a single service (use ADD)
- Bug fixes that don't change architecture
- Performance optimizations that keep the same structure
- Anything scoped to a single component (use ADD)

---

## How to Update the SAD

1. Create a branch in `designs`: `arch/update-sad-PROJ-NNN`
2. Edit only the sections that changed — keep unrelated sections untouched
3. If an ADR is required, write it first (or in the same PR)
4. Open a PR against `designs` main — architect review required before merge
5. Reference the SAD PR in the Jira ticket description or as a comment

For large changes (new service, major integration), follow the full change control process: see `change-control`.

---

## Code Review Trigger

During code review, if the architect notices:
- Code introduces a pattern or service not in the SAD
- Implementation diverges from what the SAD or an ADD specifies
- A new trade-off was made that changes the architecture

…they must either:
1. Request a SAD/ADD/ADR update before approving, or
2. Write a Jira comment with the reference for follow-up in the same sprint
