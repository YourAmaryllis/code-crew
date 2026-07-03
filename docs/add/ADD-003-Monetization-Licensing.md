# ADD-003: Monetization and Licensing Architecture

**Status:** Draft
**Date:** 2026-07-02
**Related:**
- [ADR-004: Open-Core Licensing Model](../adr/ADR-004-Open-Core-Licensing.md)
- [SAD-001: code-crew system architecture](../sad/SAD-001-code-crew.md)

---

## Model: Open-Core

The framework (Python, CrewAI wiring, OKF loader, REPL, CLI) is open source under AGPL-3.0.
The knowledge (agent prompts, task definitions, function docs, stack guides, compliance stacks)
is the product — it ships in two tiers: Community and Pro.

The framework without knowledge is useless. The knowledge without the framework is just
markdown. The value is the combination, and the Pro knowledge is what enterprises pay for.

---

## Tiers

### Community (free, open source)

Covers the basic dev loop: scaffold → implement → review.
Genuinely useful for solo developers and small teams.
Intentionally lite — functional but not production-grade for a team.

**Agents (simplified prompts — correct but shallow):**
- `engineer` — writes and tests code, follows commit conventions
- `architect` — reviews architecture and produces ADD stubs
- `qa_lead` — writes and runs tests

**Tasks:**
- `scaffold_code`, `scaffold_test` — generate initial structure
- `implementation` — implement a ticket end-to-end
- `code_review` — basic review pass (no security or compliance gate)

**Functions:**
- `coding-standards`, `branching-strategy`, `test-coverage`, `scaffold-code`, `scaffold-test`

**Stacks:**
- `python`, `go-backend`, `typescript-react` — enough for real projects

**Skills:** all four (`terse`, `strict`, `explain`, `dry-run`) — style modifiers, not content

**Commands:** `/run`, `/issue`, `/explore`, `/init`, `/design` (requirements + ADD draft only)

**What's missing** (and why users upgrade):
- No BDD cycle — the iterative PO + architect review loop that makes output team-grade
- No security review gate — no OWASP checklist, no threat model maintenance
- No compliance review — no GDPR, HIPAA, SOC2, NIST, FIPS checklist
- No DoD check — output is never validated against Definition of Done
- No staging / smoke / launch decision flow
- Agent prompts lack the methodology depth that produces enterprise-grade output
- No ops crew
- No UX / Figma flow

---

### Pro (paid)

Full enterprise SDLC pipeline. Targets teams shipping to production in regulated or
security-conscious environments.

**All Community content, plus:**

**Agents (full prompt depth — specific methodology, non-negotiable constraints):**
- `engineer` — upgraded: layer enforcement, four fetch states, WCAG AA, SDLC phase table
- `architect` — upgraded: C4/DDD/hexagonal methodology, alignment gate logic
- `qa_lead` — upgraded: BDD Gherkin authoring, coverage thresholds, reporting
- `security_lead` — OWASP ASVS L2, FIPS 140-3, SBOM, threat model maintenance
- `compliance_officer` — GDPR, HIPAA, SOC2, NIST per active compliance stack
- `devops_lead` — CI/CD pipeline config, environment management, IaC
- `release_engineer` — launch decision gate, go/no-go criteria, rollback conditions
- `chief_architect` — cross-crew alignment review, exception authority
- `ux_lead` — Figma → component spec, design token extraction, a11y review
- `product_owner` — BDD review and acceptance, story format enforcement
- `scrum_master` — sprint planning check, DoD enforcement, release notes

**Tasks (full sequences):**
- BDD cycle: `bdd_test_authoring` → `bdd_po_review` + `bdd_arch_review` → `bdd_finalization`
- Review gates: `security_review`, `compliance_review`, `dod_check`
- Staging: `promote_staging`, `staging_verification`, `smoke_test`, `launch_decision`
- Design: `design_security_input`, `design_compliance_input`, `design_chief_review`, `design_finalize`
- Verify: `verify_arch_scan`, `verify_security_scan`, `verify_compliance_scan`, `verify_domain_scan`, `verify_chief_review`, `verify_report`
- Domain: `domain_flow_discovery`, `domain_event_storming`, `domain_synthesis`, `domain_extract`
- UX: `ux_spec`, `ux_implementation`, `ux_review`
- Ops: `cicd_config`, `environment_plan`, `monitoring_setup`, `terraform_write`, `release_plan`

**Functions (enterprise):**
- `bdd-authoring`, `bdd-implementation`, `definition-of-done`, `change-control`
- `compliance-evidence`, `auditing-evidence`, `monitoring-observability`
- `release-process`, `deployment-strategy`, `environment-management`
- `domain-methodologies/` (DDD, event-storming, C4)
- `security-privacy`, `threat-dragon`

**Stacks (compliance and architecture):**
- `gdpr`, `hipaa`, `soc2`, `nist`, `fips-140-3`, `ccpa`, `cfr-part-11`
- `owasp`, `bdd-testing`, `ai-ml`
- `arch-clean`, `arch-hexagonal`, `arch-onion`, `arch-layered`
- `ecs-deployment`, `terraform-aws`, `github`, `gitlab`

**Commands:** `/verify`, `/domain`, `/ux`, plus full `/design` and full `ops/` crew

---

## Natural Upgrade Triggers

These are the moments a Community user hits the ceiling and buys:

| Trigger | What they hit |
|---|---|
| Team grows past ~3 engineers | Need the security and DoD gates to maintain quality |
| First SOC2 audit | Compliance review agent + compliance evidence function |
| GDPR or HIPAA obligation | Compliance stacks, `compliance_officer` agent |
| PO wants to write acceptance criteria | BDD cycle not in Community |
| Architect wants threat modeling | `security_lead` + threat-dragon function |
| DevOps wants the staging pipeline | Ops crew is Pro only |
| AI/ML features introduced | `ai-ml` stack (OWASP LLM Top 10, PLOT4ai) is Pro |
| Regulated industry (healthcare, finance) | Full compliance stacks required |

---

## Knowledge Protection: Supabase License Gate

Pro knowledge is **not distributed locally**. It is fetched live from a Supabase-backed
license server. Nothing is stored on the user's machine beyond a short-lived encrypted cache.

### Why not a pip package or file download?

A locally installed file can be copied and shared with zero friction. The goal is not
unbreakable DRM (no text-based DRM is) — it is to make sharing a license key auditable
and terminatable, while making file sharing impractical.

### Architecture

```
code-crew (client)                    Supabase
       │                                  │
       │  POST /functions/v1/knowledge    │
       │  { key, file, machine_id }       │
       ├─────────────────────────────────►│
       │                               Edge Function:
       │                               1. validate key (not revoked, not expired)
       │                               2. check machine_id quota (seat limit)
       │                               3. log usage
       │                               4. return file content
       │◄─────────────────────────────────┤
       │  { content: "---\nrole: ..." }   │
```

The Supabase service key never leaves the Edge Function. `code-crew` only holds a
per-customer license key — it cannot access Supabase Storage directly.

### Local cache (UX requirement)

A crew run involves 10–40 knowledge file fetches. Without caching, this would be unacceptably
slow and require constant connectivity. The cache:

- Stored at `~/.code-crew/cache/<sha256(key + filename)>`
- Encrypted with `PBKDF2(license_key + machine_id)` — useless without the license key
- TTL: 24 hours — after expiry, re-validates online before use
- Allows short offline periods (flights, poor connectivity)
- Does not survive license revocation: next cache miss hits the server and gets rejected

### Supabase schema

```sql
create table licenses (
  key         text primary key,
  org         text not null,
  tier        text not null check (tier in ('pro', 'enterprise')),
  seats       int not null default 1,
  valid_until timestamptz not null,
  revoked     bool not null default false,
  created_at  timestamptz default now()
);

create table license_usage (
  id          bigserial primary key,
  key         text references licenses(key),
  file        text not null,
  machine_id  text not null,
  called_at   timestamptz default now()
);
```

### Revocation

Set `revoked = true` on the license row. The next cache miss (within 24h at most) returns
a 403 and `code-crew` raises `LicenseError` with a message directing the user to support.

### Honest protection ceiling

| Threat | Mitigated? |
|---|---|
| Casual file sharing (copy installed files) | Yes — nothing to copy locally except encrypted cache |
| Sharing license key with colleagues | Partially — seat limits + machine_id anomaly detection; revoke on abuse |
| Network interception (mitmproxy) | No — content is plaintext over HTTPS |
| Patching the client to skip license check | No — determined attackers can always do this |
| Leaking prompt content publicly | No |

This is the same ceiling as GitHub Copilot or Spotify offline — adequate for a legitimate
market, not a solution for adversarial reverse engineering.

---

## Implementation Plan

### Phase 1 — Supabase setup
- [ ] Create `licenses` + `license_usage` tables in Supabase
- [ ] Write Edge Function: validate key → log usage → return file content
- [ ] Test revocation and seat-limit enforcement

### Phase 2 — Client integration
- [ ] `shared/license_client.py` — POST to edge function, return content, raise `LicenseError`
- [ ] `shared/okf_loader.py` — check license_client for `pro/` prefix files, fallback to community
- [ ] Encrypted local cache with 24h TTL (`~/.code-crew/cache/`)
- [ ] Config: `license.key` in `~/.code-crew/config.yaml`
- [ ] `LicenseError` surfaces cleanly in REPL with contact details

### Phase 3 — Knowledge split
- [ ] Audit every file under `*/knowledge/` and tag as `edition: community` or `edition: pro` in OKF frontmatter
- [ ] Create lite versions of `engineer.md`, `architect.md`, `qa_lead.md` for Community
- [ ] Move Pro files to Supabase Storage (keep local copies in a private branch as source of truth)
- [ ] Remove Pro content from the public repo

### Phase 4 — License provisioning
- [ ] Simple admin script or Supabase dashboard query to issue/revoke keys
- [ ] Welcome email template with key + install instructions
- [ ] `code-crew license status` command — shows tier, org, seats, valid_until

---

## Existing License Files

- `LICENSE` — AGPL-3.0 (framework)
- `COMMERCIAL.md` — dual-licensing terms, contact for commercial license
- `CLA.md` — contributor license agreement enabling dual licensing

These remain correct. The addition is the Pro knowledge tier served via Supabase —
the AGPL framework stays fully open; the Pro knowledge is proprietary content, not
covered by AGPL.
