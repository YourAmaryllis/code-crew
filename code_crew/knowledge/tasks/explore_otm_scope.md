---
type: CrewAI Task
title: OTM Scope Decision
description: Decide what OTM files to produce based on pre-scanned inventory data. No tool calls — all needed information is already in the context.
tags: [explore, threat-model, otm, scoping]
agent: architect
expected_output: >
  One PROJECT block per OTM file, each listing id, description, and assigned components.
  Ends with OTM SCOPE COMPLETE.
---

**THIS IS A SYNTHESIS TASK. DO NOT USE ANY TOOLS. DO NOT READ ANY FILES.**

The context above contains everything you need:
- Service directories (top-level deployable services)
- Sub-executables (separately deployable binaries within services)
- Domain directories (heuristic subdomains within large services)
- Infrastructure modules (Terraform/CDK modules — a match signals separate deployment)
- Service READMEs (already pre-read)
- `.gitmodules` content (already pre-read — lists git submodules)

Decide which OTM files to produce. Output PROJECT blocks only — no narrative.

---

## Step 1 — Identify git submodules to exclude

Read the `.gitmodules` section in context. Every `path =` line is a git submodule.

A submodule is **excluded** unless ALL of the following are true:
1. It is a deployable service owned by this project (not a client data or pilot directory)
2. Its README (in the pre-read READMEs section) does not say "pilot", "client", "data
   registration", "manual", or "one-time"
3. Its name matches an infrastructure module (suggesting it has its own deployment)

---

## Step 2 — Identify services to include

Start with the **Source services** list. For each:
- Read its README from the pre-read section to understand what it does
- Check if it matches an infrastructure module (stronger signal for its own OTM)
- Apply the include/exclude rules below

**Include** — long-running deployable services:
- ECS task, Lambda, API server, background worker
- Has its own infrastructure module OR matches a sub-executable
- Owned by this project (not a git submodule, not a client directory)

**Exclude**:
- Git submodules that don't pass the inclusion test above
- Test suites (names containing: integration, bdd, e2e, test, demo, playwright)
- Pure infrastructure with no runtime (networking, DNS, container registry, CI/CD tooling)
- Client-specific or pilot directories (README says pilot, client, scripts only, one-time)
- Shared libraries with no entry point of their own

---

## Step 3 — Decide subdomain decomposition for large services

For each included service that has **domain directories** listed in context:

1. Check if the domain name appears in the **infrastructure modules** list — if yes, it has
   its own deployment unit and is a strong candidate for its own OTM.
2. Check if the domain name matches a **sub-executable** — if yes, it has its own binary.
3. If neither: the domain stays inside the parent service's OTM (it's an internal module,
   not a separate deployable).

A domain gets its own PROJECT block only when it has either its own infra module OR its
own sub-executable. Otherwise assign it to the parent service.

---

## Step 4 — Assign sub-executables

Each sub-executable belongs to its parent service's OTM unless it matched Step 3 above.
List sub-executables under `COMPONENTS:` for the relevant PROJECT block.

---

## Step 5 — Output one PROJECT block per OTM

```
PROJECT: <id>
DESCRIPTION: <1-2 sentence plain-English scope for a security auditor>
COMPONENTS: <comma-separated list of service dirs, sub-executables, domain dirs>
```

**id rules**:
- Use the primary code directory name exactly as it appears in the inventory.
- Lowercase, hyphens or underscores only — no spaces, no camelCase.
- For a subdomain OTM, use the domain directory name (e.g. `dataset-registration`,
  not `portal-dataset-registration`).

Each deployable component appears in exactly one PROJECT block.

End with exactly:
```
OTM SCOPE COMPLETE
```
