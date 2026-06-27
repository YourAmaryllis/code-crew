---
name: SDLC-Product-UserJourney
description: User journey mapping process — format, who creates it, when it is updated, and how it feeds into requirements and design
metadata:
  type: process
  role: product
  phase: "3"
---

# User Journey Mapping

User journey maps are created in Phase 3, alongside the domain model. They describe how users interact with the product end-to-end, capturing their goals, actions, touchpoints, and emotional state at each step. They are the bridge between business requirements (BRD) and UX wireframes (Phase 9).

---

## When to Create or Update a User Journey

**Create a new journey when:**

- Onboarding a new user persona
- Introducing a new product flow (e.g. a new onboarding path, a new core feature)
- A major business requirement changes the way users complete a task

**Update an existing journey when:**

- New features change a step in an existing flow
- User research reveals a gap or pain point in the current journey
- Compliance requirements add steps (e.g. consent, verification)

---

## User Journey Format

User journeys are documented as a table or Mermaid diagram. Each journey includes:

| Field | Description |
|-------|-------------|
| **Persona** | Which user role (e.g. Data Analyst, Platform Admin, Customer) |
| **Scenario** | The goal the user is trying to accomplish |
| **Phases** | Named stages of the journey (e.g. Discovery → Onboarding → Activation → Retention) |
| **Steps** | Specific actions at each phase |
| **Touchpoint** | Where the interaction happens (portal, email, API, support) |
| **User feeling** | Positive / neutral / frustrated |
| **Pain points** | Friction, confusion, or blockers |
| **Opportunities** | Where we can reduce friction or delight the user |

---

## Example Journey Structure

```markdown
## Journey: Data Analyst — First Data Curation Request

### Persona
Data Analyst at a biotech company. Comfortable with data tools. Unfamiliar with HIPAA de-identification.

### Scenario
Analyst wants to submit a dataset for curation and receive de-identified output.

| Phase | Step | Touchpoint | Feeling | Pain Points | Opportunities |
|-------|------|-----------|---------|-------------|---------------|
| Discovery | Reads product docs | Website / docs | Neutral | Dense legal language | Plain-language guide |
| Onboarding | Creates account | Portal | Positive | MFA setup friction | Streamlined setup wizard |
| Request | Submits dataset | Portal upload | Anxious | Unclear progress indicator | Real-time status updates |
| Processing | Waits for curation | Email notification | Neutral | No ETA shown | ETA in status email |
| Delivery | Downloads result | Portal | Satisfied | — | — |
| Support | Questions about output | Email / Slack | Frustrated | Slow response | In-product FAQ |
```

---

## Relationship to Other Artifacts

- **BRD → User Journey**: business requirements define what the product does; user journeys show how users experience it
- **User Journey → UX Wireframes**: wireframes are designed for each step in the journey
- **User Journey → User Stories**: each journey step that involves the portal or an API becomes a candidate user story
- **User Journey → Domain Model**: personas become actors in the domain; journey steps map to use cases

---

## Storage and Tooling

User journeys are documented in:

- `designs/PLAN/` as Markdown files (linked from BRD)
- FigJam for visual maps (link stored in the relevant BRD or Jira epic)

The canonical reference is always the Markdown file in `designs/`. FigJam is a working tool, not the source of truth.

---

## AI Assistance

AI can generate draft user journey maps from:

- BRD content
- Persona descriptions
- Interview notes or sales call summaries

Prompt pattern:

``` text
Given this BRD section and these user personas, generate a user journey map table 
for [persona] accomplishing [goal]. Include phases, steps, touchpoints, feelings, 
pain points, and opportunities.
```

Human product owner reviews and refines the draft.
