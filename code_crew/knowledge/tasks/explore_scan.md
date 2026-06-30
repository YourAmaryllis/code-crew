---
type: CrewAI Task
title: Project Exploration Scan
description: Architect verifies Phase 1 detections, then discovers code structure, test structure, CI/CD workflow purposes, and entry points — producing a complete reference that all future workflow agents rely on
tags: [explore, architecture, project-scan, verification]
agent: architect
expected_output: >
  Verification lines (STACK_VERIFIED/NOT_FOUND/ADDED, COMMAND_VERIFIED/CORRECTED/NOT_FOUND/ADDED,
  CICD_VERIFIED/NOT_FOUND, TF_ROOT_VERIFIED/ENV_VERIFIED/STATE_VERIFIED/MODULES_VERIFIED/CORRECTED),
  then six DISCOVERY_BEGIN/END blocks (code_structure, test_structure, cicd_workflows, entry_points,
  architectural_components, compliance_standards), then: ARCHITECTURE_STYLE, PROJECT_SUMMARY,
  one COMPONENT line per service, then EXPLORE SCAN COMPLETE
---

You are performing a **comprehensive project exploration scan**. Your output will be saved as
`structure.md` and used by ALL future agents (engineer, QA, DevOps) when working on issues.
After this scan, agents should never need to re-discover where things live.

**Goal**: Build a complete, verified picture of the codebase so that:
- An engineer knows exactly where to add a new handler, service, model, or test
- A QA agent knows where test files live, how to run them, and how to write a new BDD scenario
- A DevOps agent knows which CI/CD workflow handles which environment

Use `workspace_reader` throughout. Always try `list_directory` before `read_file`. Never guess —
read the actual files. If a read fails, try the parent directory, then continue.

---

## Step 0 — Verify Phase 1 detections

The context contains Phase 1 auto-detection results. Verify each by reading actual files.

### Stacks

For each detected stack, check the canonical file:

| Stack | Canonical check |
|-------|----------------|
| go-backend | `go.mod` exists at root or in a service dir |
| typescript-react | `package.json` with `react` or `@types/react` in deps, or `.tsx` files exist |
| python | `requirements.txt`, `pyproject.toml`, or `setup.py` exist |
| terraform | `*.tf` files exist |
| terraform-aws | `*.tf` files contain `provider "aws"` |
| ecs-deployment | `*ecs*.tf`, `*task-definition*.json`, or ECS resource in tf files |
| bdd-testing | `*.feature` files exist |
| java | `pom.xml` or `build.gradle` exists |
| rust | `Cargo.toml` exists |

Use `workspace_reader` with `operation: find_files` or `read_file` to check.

Output one line per stack:
```
STACK_VERIFIED: <stack>: <file that confirms it>
STACK_NOT_FOUND: <stack>: <what you looked for and didn't find>
STACK_ADDED: <stack>: <file that reveals an undetected stack>
```

### Commands

For each detected command, verify the source file actually contains it:
- If it references a `Makefile` target: confirm the target exists in `Makefile`
- If it references `npm run <script>`: confirm the script key exists in the relevant `package.json`
- If it uses `go test`: confirm `go.mod` exists
- If it references `cd <path>`: confirm that path exists

Output:
```
COMMAND_VERIFIED: <key>: <command>
COMMAND_CORRECTED: <key>: <corrected_command>: <reason>
COMMAND_NOT_FOUND: <key>: <reason>
COMMAND_ADDED: <key>: <command>: <source>
```

### CI/CD

For each detected CI/CD method, confirm the config files exist:
- `github-actions`: confirm `.github/workflows/` exists and list the workflow filenames
- `gitlab-ci`: confirm `.gitlab-ci.yml` exists
- Others: confirm the respective config file exists

Output:
```
CICD_VERIFIED: <method>: <detail>
CICD_NOT_FOUND: <method>: <what was missing>
CICD_ADDED: <method>: <what you found that wasn't detected>
```

### Terraform structure (if detected)

1. Confirm `tf_root` directory exists
2. For each reported environment, confirm its subdirectories exist
3. Read one `backend.tf` and confirm: S3 bucket, region, state key pattern, AWS profile
4. List and confirm the modules directory

Output:
```
TF_ROOT_VERIFIED: <path>
TF_ENV_VERIFIED: <env>: <layers confirmed>
TF_STATE_VERIFIED: bucket=<bucket>, region=<region>, key_pattern=<pattern>, profile=<profile>
TF_MODULES_VERIFIED: <count> modules in <path>: <module1>, <module2>, ...
TF_CORRECTED: <field>: <corrected_value>: <reason>
TF_NOT_FOUND: <what was reported but doesn't exist>
TF_DISCOVERED: <what you found that wasn't in Phase 1>
```

---

## Step 1 — Read README and key docs

Use `workspace_reader` to read (try in order, stop when found):
- `README.md` or `README.rst` at root
- `docs/README.md`

Read at most 2 files. If none exist, proceed with the tree only.

---

## Step 2 — Code structure discovery

**Goal**: Document where each type of code lives so an engineer picking up a ticket knows
exactly where to add new code without exploring the repo.

For each verified backend/service stack (Go, Python, Java, etc.):

1. Use `workspace_reader` with `operation: list_directory` on the main source directory
   (e.g., the `internal/` or `src/` directory of the service)
2. For subdirectories with names like `handlers`, `api`, `services`, `service`,
   `repository`, `store`, `models`, `entities`, `domain`, `adapters`: list them to see their contents
3. Read 1-2 existing source files (a handler and a service) to understand naming conventions
4. Document the layer layout and where new files of each type should be added

For each verified frontend stack (TypeScript/React, Vue, etc.):

1. List the `src/` directory
2. Note the component directory, page directory, hooks directory, API client directory
3. Identify whether files use barrel exports (`index.ts`), co-located styles, etc.

Output a discovery block containing a markdown section per stack:

```
DISCOVERY_BEGIN: code_structure
## Code structure

### <stack-name> (<root-directory>/)

**Layer layout**:

| Layer | Directory | Purpose |
|-------|-----------|---------|
| HTTP handlers | `<path>` | <what goes here> |
| Business logic | `<path>` | <what goes here> |
| ... | | |

**Naming conventions**:
- New handler: `<example path and file name pattern>`
- New service: `<example path and file name pattern>`

**Key source files read**: `<file1>`, `<file2>`

[repeat for each stack]
DISCOVERY_END: code_structure
```

If you cannot find a clear layer separation, document what you observe — even a flat
`src/` layout is useful to document.

---

## Step 3 — Test structure discovery

**Goal**: Build a complete picture of every test suite in the repo — unit, integration,
smoke, BDD, e2e — so an engineer or QA agent knows exactly where tests live, how they
are named, what framework runs them, and which command or script executes each suite.
**Do not assume any paths; discover them by reading actual files.**

### 3a — Find test runner scripts and config

First, look for test execution mechanisms across the whole repo:

1. **Shell scripts**: use `find_files` with pattern `**/run*test*.sh`, `**/run*bdd*.sh`,
   `**/run*integration*.sh`, `**/scripts/*.sh`. Read any that look test-related.
2. **Makefile targets**: if a `Makefile` was detected, read it and list targets that
   contain the words `test`, `bdd`, `integration`, `smoke`, or `e2e`.
3. **package.json scripts**: for any `package.json` that contains test-related script keys
   (`test`, `test:unit`, `test:e2e`, `test:integration`, `vitest`, `jest`, `playwright`),
   note the exact command.
4. **Config files**: look for `jest.config.*`, `vitest.config.*`, `playwright.config.*`,
   `pytest.ini`, `pyproject.toml` (for `[tool.pytest]`), `.godog.yml`.

### 3b — Locate test files

Use `find_files` to discover where tests actually live — do not guess paths:

- Go: `*_test.go` (note which directories they appear in — some may be co-located with
  source, others in a dedicated directory like `integration/`)
- TypeScript/JavaScript: `*.test.tsx`, `*.test.ts`, `*.test.js`, `*.spec.ts`, `*.spec.js`
- Python: `test_*.py`, `*_test.py`
- BDD: `*.feature` (the context provides detected feature dirs — verify each one exists
  and read one feature file to understand the format)
- Step definitions: for each `.feature` dir found, look for `*_steps.go`, `*steps*.go`,
  `steps_*.go`, `*_test.go` in the same or sibling directory

### 3c — Classify each test suite

For every distinct test suite discovered, determine:
- **Type**: unit | integration | BDD | smoke | e2e | other
- **Location**: actual directory path (discovered, not assumed)
- **Framework**: go test / godog / vitest / jest / playwright / pytest / other
- **How to run**: prefer the discovered script or Makefile target if one exists;
  otherwise document the direct command (`go test ./path/...`, `npm test`, etc.)
- **How to run a single test**: the command to run one test case or one feature file
- **Config file**: path to the framework config if one exists

If a `scripts/` directory exists near the test suite, list all `.sh` files in it —
they often contain the canonical execution commands with environment setup.

Output a discovery block:

```
DISCOVERY_BEGIN: test_structure
## Test structure

### <Suite name> — <type>

- **Location**: `<discovered path>`
- **Framework**: `<framework>`
- **Run all**: `<command or script path>`
- **Run single**: `<command>` (e.g., go test ./path -run TestName, or feature file path)
- **Config**: `<config file path if any>`
- **Scripts available**: `<script1>`, `<script2>` (list scripts/ files if present)

[one section per distinct test suite — do not merge suites from different directories
 or frameworks into one section]
DISCOVERY_END: test_structure
```

---

## Step 4 — CI/CD workflow analysis

**Goal**: Document what each CI/CD workflow does so a DevOps agent knows which workflow
handles which service, environment, and action.

If GitHub Actions was detected:

1. List all files in `.github/workflows/` — these were already provided in context
2. Read up to **6** workflow files, prioritizing those with names suggesting:
   deploy, build, push, release, integration, staging, prod
3. For each workflow read, note:
   - `on:` trigger (push, pull_request, workflow_dispatch, schedule)
   - Target branch pattern (if applicable)
   - What services or images it builds/deploys
   - Target environment (dev, staging, prod, or all)
   - Key steps (ECR push, ECS deploy, SSH, etc.)

If GitLab CI was detected: read `.gitlab-ci.yml` and extract the same information.

Output a discovery block:

```
DISCOVERY_BEGIN: cicd_workflows
## CI/CD workflows

### GitHub Actions (`.github/workflows/`)

| Workflow file | Trigger | Purpose | Environment |
|--------------|---------|---------|-------------|
| `<filename>` | <push to main / PR / manual> | <what it does> | <env> |
...

**Notes**:
- <any important patterns, e.g. "all deploy workflows require manual approval for prod">
- <e.g. "BDD tests triggered on PR and can be run manually via workflow_dispatch">
DISCOVERY_END: cicd_workflows
```

If no CI/CD workflows could be read, output a block noting what was found:
```
DISCOVERY_BEGIN: cicd_workflows
## CI/CD workflows

No workflow files could be read. Detected methods: <list>.
DISCOVERY_END: cicd_workflows
```

---

## Step 5 — Entry points and local dev setup

**Goal**: Document how each service starts so an engineer can run the project locally
and so agents know the exact entry point file to trace when debugging.

For each service component:

1. Look for `main.go`, `cmd/*/main.go`, `main.py`, `app.py`, `server.py`,
   `main.tsx`, `index.ts`, or equivalent entry point files
2. Note the start command (from README, Makefile, or package.json `start` script)
3. Note key environment variables (from `.env.example`, README, or config loading code)

Output a discovery block:

```
DISCOVERY_BEGIN: entry_points
## Entry points

| Service | Entry point file | Start command | Notes |
|---------|-----------------|---------------|-------|
| <name> | `<path>` | `<command>` | <env vars, ports, etc.> |
...
DISCOVERY_END: entry_points
```

---

## Step 5c — Architectural component discovery

**Goal**: Map SAD decomposition components to actual code so that the security scan knows which
components need threat models and the arch scan knows what should match the SAD.

1. Use `workspace_reader` to read `designs/SAD/SAD-3-Decomposition-View.md` (the Element Catalog
   table in section 3.2). If no SAD exists, use the service directories discovered in Step 2.
2. For each SAD component: identify the corresponding code directory/directories in the project.
3. Note any code services that do not appear in the SAD (they may be newer than the SAD).
4. Note any SAD components with no corresponding code directory (possible gap or renamed).

Output a discovery block:

```
DISCOVERY_BEGIN: architectural_components
## Architectural components

Derived from SAD decomposition view and current code structure.
SAD source: `designs/SAD/SAD-3-Decomposition-View.md`

| SAD Component | Code directory | Type | Notes |
|---------------|----------------|------|-------|
| LooporaData Portal | `portal/` | deployable service | ... |
| Container Instrumentation Pipeline | `attestation/` | deployable service | worker + server |
| ...  | | | |

**In code but not in SAD** (newer than SAD or not yet documented):
- `healthcare-calculator/` — Healthcare pricing calculator service
- `panome/` — MCP-based data discovery service

**In SAD but not in code** (removed, renamed, or not yet implemented):
- (list if any)
DISCOVERY_END: architectural_components
```

If no SAD exists:
```
DISCOVERY_BEGIN: architectural_components
## Architectural components

No SAD found. Components derived from code structure only.

| Component | Directory | Type |
|-----------|-----------|------|
| <name> | `<dir>/` | deployable service |
...
DISCOVERY_END: architectural_components
```

---

## Step 5b — Compliance standards

**Goal**: Confirm the Python-detected compliance standards and discover any the scan missed,
so the audit crew knows which regulatory frameworks apply without re-scanning every time.

The task context includes **Phase 1 compliance standards** detected by keyword scan of designs/
and docs/. Verify these by reading the actual files, then check for any not yet detected.

Standards to look for — scan designs/, docs/, root `*.md`, and any `SOP/` files:

| Standard | Keywords to find |
|----------|-----------------|
| HIPAA    | hipaa, phi, protected health information, hitech |
| SOC 2    | soc 2, soc2, trust service criteria |
| GDPR     | gdpr, general data protection, data subject, right to erasure |
| CCPA     | ccpa, california consumer privacy, right to know |
| PCI-DSS  | pci dss, pci-dss, cardholder data, payment card industry |
| FIPS     | fips 140, fips-140 |

Read at most 6 documents. If a document mentions a standard, mark it confirmed.

Output a discovery block:

```
DISCOVERY_BEGIN: compliance_standards
## Compliance standards

**Detected and confirmed**:
- HIPAA — confirmed in `designs/SOP/...` (PHI handling requirements)
- SOC 2 — confirmed in `designs/SOP/...` (trust service criteria)

**Detected but unconfirmed** (found no clear keyword match after reading files):
- (list any if applicable)

**Not detected** (no mentions found):
- GDPR, CCPA, PCI-DSS, FIPS (no mentions found in scanned docs)

**Files scanned**: `<file1>`, `<file2>`, ...
DISCOVERY_END: compliance_standards
```

If none are found after checking, say so explicitly:
```
DISCOVERY_BEGIN: compliance_standards
## Compliance standards

No compliance standards detected in designs/ or docs/.
DISCOVERY_END: compliance_standards
```

---

## Step 6 — Architecture assessment

Consider the directory tree. Look for:
- **Hexagonal**: explicit `ports/` + `adapters/` separation; no business logic in transport layer
- **Clean**: `usecases/` with isolated business rules; `entities/`, `adapters/`
- **Onion**: concentric rings — `domain/` innermost, `application/`, `infrastructure/`
- **Layered**: `handlers/` or `controllers/` + `services/` + `repository/` — classic three-tier
- **Undetected**: none of the above is clearly identifiable

Output:
```
ARCHITECTURE_STYLE: <style>
```

---

## Step 7 — Project summary

Write 1-2 sentences describing what this project does and who uses it.
Be specific: name the domain, not just the technology.

Output:
```
PROJECT_SUMMARY: <description>
```

---

## Step 8 — Component descriptions

For each candidate service/component directory from Phase 1, skim its README or first
30 lines of its main source file. Write one sentence describing what it does.

Note whether it is a deployable service, a shared library, a CLI, or an integration test suite.

Output one line per component:
```
COMPONENT: <dir_name>: <description>
```

---

## On tool failure

Log the error, try once with an alternative (list parent dir if read fails, use `find_files`
before `read_file`). Skip and continue — never block the scan on a single failure. Never use
absolute paths. Note any skipped items in the DISCOVERY blocks.

---

## Step 9 — Output EXPLORE SCAN COMPLETE

After all steps, output exactly:
```
EXPLORE SCAN COMPLETE
```
