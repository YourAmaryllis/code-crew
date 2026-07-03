# ADR-004: Open-Core Licensing Model

**Status:** Accepted
**Date:** 2026-07-02
**Related:** [ADD-003: Monetization and Licensing Architecture](../add/ADD-003-Monetization-Licensing.md)

---

## Context

code-crew consists of two separable layers:

1. **Framework** — Python CLI, CrewAI wiring, OKF loader, REPL, tool library
2. **Knowledge** — agent prompts, task definitions, function docs, stack guides, compliance stacks

The framework alone is not useful without knowledge; the knowledge is not executable without the framework. The value to enterprise users is the combination — specifically the depth of the Pro knowledge tier.

Options for distribution:

- **Fully open source**: maximises adoption but enables direct competitors to take the knowledge without contributing back
- **Fully proprietary**: limits adoption and contradicts the tool's nature as a development aid
- **Open-core**: framework open (AGPL-3.0), knowledge split into Community (free) and Pro (paid, served via license server)

---

## Decision

Adopt open-core:

1. **Framework** is open source under AGPL-3.0 — this includes all Python code, the OKF loader, REPL, tool library, and CLI
2. **Community knowledge** is freely distributed in the public repository — simplified agent prompts covering the basic dev loop (scaffold → implement → review)
3. **Pro knowledge** is proprietary content served live from a license server — full agent depth, compliance stacks, BDD cycle, security review, staging flow, domain modeling, UX flow

Pro knowledge is **not distributed locally** (no pip package, no file download). It is fetched from a Supabase-backed license server with a 24-hour encrypted local cache. See [ADD-003](../add/ADD-003-Monetization-Licensing.md) for the full architecture.

---

## Considered Options

| Option | Pros | Cons |
|--------|------|------|
| Fully open source | Maximum adoption; community contributions | Knowledge freely forkable; no revenue model; enables direct clones |
| Fully proprietary | Full control over knowledge | Limits adoption; harder to build community trust |
| **Open-core (chosen)** | Attracts contributors via open framework; protects knowledge product; revocable licenses | Supabase dependency adds operational surface; limited DRM ceiling (same as any SaaS) |

---

## Consequences

**Positive:**
- Framework can attract community contributions (bug fixes, new stacks, new tool backends) without giving away the knowledge product
- License revocation is possible and effective within 24 hours
- AGPL copyleft on the framework prevents proprietary forks of the framework itself
- Community tier is genuinely useful — generates adoption and word of mouth

**Negative / Risks:**
- Supabase dependency adds operational surface (managed service must remain available)
- Determined attackers can intercept HTTPS or patch the client — this is the same ceiling as any SaaS with an offline mode
- Community tier must be genuinely useful, or users won't install and discover Pro
- Knowledge split (Community vs Pro tagging) adds maintenance overhead when editing knowledge files

**Operational:**
- `shared/license_client.py` — fetches Pro knowledge from Supabase Edge Function
- `shared/okf_loader.py` — checks license for `pro/` prefix files; falls back to community
- `~/.code-crew/cache/` — encrypted 24h cache keyed by `PBKDF2(license_key + machine_id)`
- `code-crew license status` command — shows tier, org, seats, valid_until
- License revocation: set `revoked = true` in Supabase; takes effect within 24h (next cache miss)
