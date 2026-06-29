---
type: CrewAI Task
title: Project Exploration Scan
description: Architect verifies Phase 1 detections by reading actual files, then assesses architecture, summarises the project, and describes each service component
tags: [explore, architecture, project-scan, verification]
agent: architect
expected_output: >
  One VERIFIED/CORRECTED/NOT_FOUND line per detected item (stacks, commands, CI/CD, Terraform),
  then:
  ARCHITECTURE_STYLE: <clean|hexagonal|onion|layered|undetected>
  PROJECT_SUMMARY: <1-2 sentence description of what this project does>
  COMPONENT: <dir_name>: <one-sentence description>
  ...one COMPONENT line per service directory...
  EXPLORE SCAN COMPLETE
---

You are performing a project exploration scan. The context contains Phase 1 auto-detection
results produced by a pure file-system scan. Your job is to:

1. **Verify every detected item** by reading the actual files — do not trust the detection blindly
2. Assess the architecture pattern
3. Summarise the project
4. Describe each service/component

---

## Step 0 — Verify Phase 1 detections

The context provides detected stacks, commands, CI/CD methods, and infrastructure structure.
For each item, use `workspace_reader` to confirm it exists and is correct.
Output one verification line per item using the formats below.

### Stacks

For each detected stack, check the canonical file:

| Stack | Check |
|-------|-------|
| go-backend | `go.mod` exists at root or in a service dir |
| typescript-react | `package.json` with `react` or `@types/react` in deps, or `.tsx` files exist |
| python | `requirements.txt`, `pyproject.toml`, or `setup.py` exist |
| terraform | `*.tf` files exist |
| terraform-aws | `*.tf` files contain `provider "aws"` or `source = "hashicorp/aws"` |
| ecs-deployment | `*ecs*.tf`, `*task-definition*.json`, or ECS resource in tf files |
| bdd-testing | `*.feature` files exist |
| java | `pom.xml` or `build.gradle` exists |
| rust | `Cargo.toml` exists |

Use `workspace_reader` with `operation: find_files` or `read_file` to check.

Output:
```
STACK_VERIFIED: <stack>: <file that confirms it>
STACK_NOT_FOUND: <stack>: <what you looked for and didn't find>
STACK_ADDED: <stack>: <file that reveals an undetected stack>
```

### Commands

For each detected command, verify the source file actually contains that command:

- If a command references a `Makefile` target: confirm the target exists in `Makefile`
- If a command references `npm run <script>`: confirm the `scripts` section in the relevant `package.json` has that key
- If a command uses `go test`: confirm `go.mod` exists
- If a command references `cd <path>`: confirm that path exists in the repo

Output:
```
COMMAND_VERIFIED: <key>: <command>
COMMAND_CORRECTED: <key>: <corrected_command>: <reason>
COMMAND_NOT_FOUND: <key>: <reason>
```

If you find a command that wasn't detected (e.g., a `test` target in a Makefile that was missed), add:
```
COMMAND_ADDED: <key>: <command>: <source>
```

### CI/CD

For each detected CI/CD method, confirm the config files exist:

- `github-actions`: list `.github/workflows/` directory, output the workflow filenames
- `gitlab-ci`: confirm `.gitlab-ci.yml` exists
- `terraform`: confirm `*.tf` files exist (already covered by stack check)
- Others: confirm the respective config file exists

Output:
```
CICD_VERIFIED: <method>: <detail — e.g. "12 workflows in .github/workflows/">
CICD_NOT_FOUND: <method>: <what was missing>
CICD_ADDED: <method>: <what you found that wasn't detected>
```

### Terraform structure (if terraform stack detected)

If Terraform was detected, verify the infrastructure structure:

1. Confirm the reported `tf_root` directory exists by listing it
2. For each reported environment (dev/staging/prod/etc), confirm its subdirectories exist
3. Read one `backend.tf` from within the tf root and confirm:
   - The S3 bucket name
   - The region
   - The state key pattern
   - The AWS profile (if any)
4. List the modules directory and confirm the module list is accurate

Output:
```
TF_ROOT_VERIFIED: <path>
TF_ENV_VERIFIED: <env>: <layers confirmed>
TF_STATE_VERIFIED: bucket=<bucket>, region=<region>, key_pattern=<pattern>, profile=<profile>
TF_MODULES_VERIFIED: <count> modules in <path>: <module1>, <module2>, ...
TF_CORRECTED: <field>: <corrected_value>: <reason>
TF_NOT_FOUND: <what was reported but doesn't exist>
```

If Terraform is detected but no structure was reported in Phase 1, discover and report it:
```
TF_DISCOVERED: <what you found>
```

---

## Step 1 — Read README and entrypoints

Use `workspace_reader` to try reading (in order, stop when found):
- `README.md` or `README.rst` at root
- `docs/README.md`
- The main entrypoint: `main.go`, first `cmd/*/main.go` match, `main.py`, `app.py`, `server.py`, `index.ts`, `index.js`

Read at most 3 files. If none exist, proceed with the tree only.

---

## Step 2 — Architecture assessment

Consider the directory tree in your context. Look for:
- **Hexagonal** (Ports & Adapters): explicit `ports/` (or `driving/`/`driven/`) separation from domain logic; `adapters/` directory; no business logic in transport layer
- **Clean Architecture**: `usecases/` or `use_cases/` with business rules isolated from frameworks; `entities/`, `adapters/`
- **Onion**: concentric rings — `domain/` innermost, `application/`, `infrastructure/`; dependencies point inward only
- **Layered**: `handlers/` or `controllers/` + `services/` + `repository/` or `storage/` — classic three-tier
- **Undetected**: none of the above is clearly identifiable

Use `knowledge_reader` to load `stacks/arch-<style>.md` if you identify a style, to confirm your assessment matches the definition.

Output:
```
ARCHITECTURE_STYLE: <style>
```

If Phase 1 detected a style and you agree, output the same. If you disagree, output your assessment. If genuinely undetected, output `undetected`.

---

## Step 3 — Project summary

From the README / entrypoint / tree, write 1-2 sentences describing what this project does and who uses it. Be specific: name the domain, not just the technology.

Output:
```
PROJECT_SUMMARY: <description>
```

---

## Step 4 — Component descriptions

The context lists candidate service/component directories from Phase 1. For each, use `workspace_reader` to skim its README (if any) or the first 30 lines of its main source file. Write one sentence describing what the component does.

Output one line per component:
```
COMPONENT: <dir_name>: <description>
```

If a directory is a shared library or utility (not a deployable service), note that explicitly.

---

## On tool failure

Log the error, try once with an alternative (list parent dir if read fails, use `find_files` before `read_file`). Skip and continue — never block the scan on a single failure. Never use absolute paths. Note any skipped items in the output.

---

## Step 5 — Output EXPLORE SCAN COMPLETE
