# code-crew Roadmap

Current date: 2026-06-26. Items marked ✅ are done. Items without a mark are pending.

---

## ✅ 1. Design flow (`/design <KEY>`)

Five-task sequential crew: architect + security_lead + compliance_officer produce ADD/ADR/TMD stub before any code is written.

Tasks: `design_requirements` → `design_add_draft` → `design_security_input` → `design_compliance_input` → `design_finalize`

`design_finalize` commits files and posts a comment to the issue tracker. Ends with `DESIGN COMPLETE` or `DESIGN BLOCKED`.

---

## ✅ 2. OTM / IriusRisk — verified + import instructions added

- OTM YAML at `designs/TMD/` — confirmed
- `functions/threat-dragon.md`: references https://github.com/iriusrisk/OpenThreatModel in frontmatter; IriusRisk import section added (StartLeft CLI + REST API)
- `stacks/ai-ml.md`: OWASP LLM Top 10 + PLOT4ai mandatory coverage — confirmed; fixed stale path `designs/threat-models/<service>.json` → `designs/TMD/<service>.yaml`
- `security_lead.md` Step 4: PLOT4ai + LINDDUN selection — confirmed

---

## ✅ 3. README updated

README now reflects: YAML config, `/design` + `/issue` commands, designs-as-submodule, OTM, Linear/GitHub Issues, stack auto-detection.

---

## ✅ 5. UX / Figma flow (`/ux <KEY>`)

**Decision needed:** Figma-to-code vs code-to-Figma? Recommendation: **Figma → code** (design is the source of truth; code follows). Workflow:

1. Designer creates Figma component/screen
2. `/ux <KEY>` crew reads the Figma URL from the ticket (already extracted into `ticket.figma_url`)
3. UX Lead agent uses Figma REST API (or MCP) to fetch frame JSON → produces component spec
4. Engineer generates component code matching the spec
5. QA Lead verifies rendered output against Figma frame (screenshot diff or accessibility check)

**New agent: UX Lead** — Figma literacy, component decomposition, design token extraction, accessibility.

**Implementation plan:**

- [ ] `code_crew/knowledge/agents/ux_lead.md` — role: UX Lead; tools: knowledge_reader, workspace_reader, ask_human
- [ ] `code_crew/knowledge/tasks/ux_spec.md` — fetch Figma frame, extract components, tokens, states, a11y notes
- [ ] `code_crew/knowledge/tasks/ux_implementation.md` — engineer generates component from UX spec
- [ ] `code_crew/knowledge/tasks/ux_review.md` — UX Lead verifies component matches spec; QA checks a11y
- [ ] `code_crew/crew.py` — `build_ux_crew()`
- [ ] `code_crew/repl.py` — `/ux <KEY>` command → `_start_ux()`
- [ ] `shared/tools/figma_reader.py` — `FigmaReaderTool`: calls Figma REST API, returns frame JSON (requires `FIGMA_TOKEN` in config)
- [ ] Config: `figma.token` in YAML → `FIGMA_TOKEN` env via `_ENV_MAP`
- [ ] README: add `/ux` to slash commands table

**Open question:** Figma Dev Mode / REST API returns design tokens — do we extract them into a `tokens.json` / CSS vars? Recommend yes: `ux_spec` task outputs a `design-tokens.json` alongside the spec.

---

## ✅ 6. MCP support + `/mcp` command

**Scope:** code-crew agents can call MCP tools (e.g. Figma MCP, Browserbase, Linear MCP). `/mcp` command lets the user manage active MCP server connections within the REPL session.

**Implementation plan:**

- [ ] `shared/mcp_registry.py` — loads MCP server configs from `~/.code-crew/mcp.yaml`; starts/stops server processes via stdio transport
- [ ] `~/.code-crew/mcp.yaml` schema:
  ```yaml
  servers:
    figma:
      command: npx @figma/mcp-server
      env:
        FIGMA_TOKEN: ${FIGMA_TOKEN}
    linear:
      command: npx @linear/mcp-server
  ```
- [ ] `shared/tools/mcp_tool.py` — `MCPClientTool`: CrewAI tool wrapper that proxies calls to an active MCP server
- [ ] `code_crew/repl.py` — `/mcp list`, `/mcp connect <name>`, `/mcp disconnect <name>`, `/mcp status`
- [ ] Agent wiring: agents can receive `MCPClientTool` instances; which MCP tools an agent gets is config-driven (not hardcoded)
- [ ] README: add `/mcp` to slash commands, add "MCP servers" section

**Note on Claude plugins:** Claude plugins are not the same as MCP — they're Claude.ai browser extensions and can't be called from code. No action needed. MCP is the right integration surface here.

---

## ✅ 6b. Skills — agent output style modifiers

**Scope:** OKF skill files in `knowledge/skills/` that agents load via `CODE_CREW_SKILLS` env var. `/skill` REPL command activates/deactivates skills per session.

**Implemented:**
- `knowledge/skills/terse.md` — verdict first, bullet findings, no filler
- `knowledge/skills/strict.md` — OWASP ASVS L3, explicit evidence per gate item
- `knowledge/skills/explain.md` — every decision includes WHY + alternatives
- `knowledge/skills/dry-run.md` — `WOULD RUN`/`WOULD WRITE` preview mode
- `crew.py` — `_load_active_skills()` injected into all three context builders
- `repl.py` — `/skills`, `/skill <name>`, `/skill off [name]` commands
- README — Skills section + commands table rows

---

## ✅ 7. Code architecture patterns

**Scope:** clean (default), hexagonal, onion — engineers follow the pattern matching the project config.

**Implementation plan:**

- [ ] Config: `architecture.style: clean | hexagonal | onion` → `ARCHITECTURE_STYLE` env
- [ ] `code_crew/knowledge/stacks/arch-clean.md` — Clean Architecture rules: entities → use cases → interfaces → frameworks; dependency rule; no framework imports in domain
- [ ] `code_crew/knowledge/stacks/arch-hexagonal.md` — Ports & adapters; domain in center; driven/driving adapters; no infra in domain
- [ ] `code_crew/knowledge/stacks/arch-onion.md` — Onion Architecture; domain model core; domain services; application services; infrastructure outer ring
- [ ] `shared/config.py` — add `architecture.style` to `_ENV_MAP`
- [ ] `/explore` — detect existing architecture pattern from file structure (e.g. `internal/domain/`, `core/`, `ports/` dirs) and write to `.code-crew/structure.md`
- [ ] `code_crew/crew.py` — `_format_context()` includes active arch style; engineer and architect agents load the relevant `arch-*.md` stack doc via KnowledgeReaderTool
- [ ] README: add "Architecture patterns" section

---

## ✅ 8. API standards (OpenAPI / Swagger)

**Scope:** crews produce and maintain OpenAPI specs; stack-specific tooling (go-swagger, FastAPI auto-gen, etc.).

**Implementation plan:**

- [ ] `code_crew/knowledge/functions/api-standards.md` — process doc: OpenAPI 3.1 structure, versioning, naming conventions (`/v1/resources/{id}`), error schema, pagination, auth headers
- [ ] `code_crew/knowledge/stacks/go-backend.md` — add: use `swaggo/swag` to generate spec; `go generate ./...` updates `docs/swagger.json`
- [ ] `code_crew/knowledge/stacks/python.md` — add: FastAPI auto-generates spec at `/openapi.json`; export with `python -m scripts.export_openapi`
- [ ] `code_crew/knowledge/stacks/typescript-react.md` — add: API client generated from spec via `openapi-typescript`
- [ ] `code_crew/knowledge/tasks/implementation.md` — Step N: "If stack has API standard, update/generate OpenAPI spec and commit it"
- [ ] `shared/tools/api_spec_tool.py` — `ApiSpecTool`: reads `docs/swagger.json` or `openapi.yaml`; checks for spec drift vs route handlers
- [ ] README: add "API standards" to structure section

---

## ✅ 9. DB schema management

**Scope:** per-stack migration tool; crew generates migration files, not raw SQL applied directly.

| Stack | Tool | Config key |
|-------|------|-----------|
| `python` | alembic | `db.migration_tool: alembic` |
| `go-backend` | goose or atlas | `db.migration_tool: goose` |
| default | atlas (cross-stack) | `db.migration_tool: atlas` |

**Implementation plan:**

- [ ] Config: `db.migration_tool`, `db.schema_path` → `DB_MIGRATION_TOOL`, `DB_SCHEMA_PATH`
- [ ] `code_crew/knowledge/functions/db-schema.md` — process doc: migration naming (`YYYYMMDDHHMMSS_description`), rollback requirement, never edit applied migrations, schema review checklist
- [ ] `code_crew/knowledge/stacks/python.md` — add alembic section: `alembic revision --autogenerate -m "description"`, review before applying, `alembic upgrade head` in CI
- [ ] `code_crew/knowledge/stacks/go-backend.md` — add goose section: `goose create description sql`, `goose up`
- [ ] `code_crew/knowledge/tasks/implementation.md` — Step N: "If feature touches DB schema, generate migration file; do NOT apply migrations"
- [ ] `/explore` — detect migration tool from existing files (`alembic.ini`, `*.goose`, `atlas.hcl`) and write to structure
- [ ] README: add "DB schema management" table

---

## ✅ 10. Enhanced `/init`

**Scope:** `/init` scaffolds `.code-crew/config.yaml` then auto-detects and writes: db migration tool, schema path, testing framework, BDD flag, API doc standard, architecture style.

**Implemented in:** `code_crew/repl.py` — `_detect_project()` + `_run_init()`

**Detection signals and config keys written:**

| Signal | Config key |
|--------|-----------|
| `alembic.ini` | `db.migration_tool: alembic` |
| `-- +goose` header in `.sql` files | `db.migration_tool: goose` |
| `atlas.hcl` / `atlas.sum` | `db.migration_tool: atlas` |
| `migrations/` dir | `db.schema_path: migrations/` |
| `pytest.ini` or `[tool.pytest]` in `pyproject.toml` | `testing.framework: pytest` |
| `jest.config.*` | `testing.framework: jest` |
| `go.mod` (fallback) | `testing.framework: go-test` |
| `*.feature` files | `testing.bdd: true` |
| `docs/swagger.json` / `openapi.yaml` | `api.doc_standard: openapi` |
| `ports/` + `driving/`/`driven/` | `architecture.style: hexagonal` |
| `domain/model/` + `application/` | `architecture.style: onion` |
| `usecases/` or `domain/` + `adapters/` | `architecture.style: clean` |

Appended to `.code-crew/config.yaml` under `# Auto-detected by /init`. Idempotent — block written only once.

**How to test:**

```bash
# 1. In a scratch directory with known signals:
mkdir /tmp/test-init && cd /tmp/test-init
touch alembic.ini
mkdir -p pytest.ini migrations src/domain src/adapters

# 2. Run init (answer prompts: name=test, tracker=jira, key=TEST)
code-crew
/init

# 3. Verify .code-crew/config.yaml contains:
cat .code-crew/config.yaml
# Expected auto-detected block:
# db:
#   migration_tool: alembic
#   schema_path: migrations/
# testing:
#   framework: pytest
# architecture:
#   style: clean

# 4. Run again — should not duplicate the auto-detected block
/init
diff <(cat .code-crew/config.yaml) <(cat .code-crew/config.yaml)  # no double block

# 5. Test goose detection:
mkdir /tmp/test-goose && cd /tmp/test-goose
echo "-- +goose Up" > migrations/001_init.sql
code-crew && /init
# Expected: db.migration_tool: goose
```

**Also verify:** `testing` and `api` sections present in `.config.example.yaml` (they are).

---

## ✅ 11. `/verify` flow — compliance check

**Scope:** Full codebase audit — architect, security lead, compliance officer each scan their domain. Chief architect (same architect agent) reviews findings and can exempt items. Result is a report + optional issue creation.

**Flow:**

```
verify_arch_scan → verify_security_scan → verify_compliance_scan
→ verify_chief_review   (architect: approve, exempt, or require fix for each finding)
→ verify_report         (scrum_master: compile final report)
→ [REPL prompt] "Open issues for unfixed findings? [y/N]"
```

**Implementation plan:**

- [ ] `code_crew/knowledge/tasks/verify_arch_scan.md` — architect scans for architecture violations (dependency rule, layer crossing, dead code)
- [ ] `code_crew/knowledge/tasks/verify_security_scan.md` — security_lead: OTM threat coverage gaps, OWASP checklist, hardcoded secrets scan, SBOM check
- [ ] `code_crew/knowledge/tasks/verify_compliance_scan.md` — compliance_officer: data retention, consent, audit trails, GDPR/HIPAA/SOC2 checklist
- [ ] `code_crew/knowledge/tasks/verify_chief_review.md` — architect reviews consolidated findings; outputs list of: PASS / EXEMPT (with reason) / REQUIRED (must fix)
- [ ] `code_crew/knowledge/tasks/verify_report.md` — scrum_master compiles findings into markdown report at `.code-crew/verify-report-YYYYMMDD.md`
- [ ] `code_crew/crew.py` — `build_verify_crew()`
- [ ] `code_crew/repl.py` — `/verify` → `_start_verify()`: runs crew, prints report path, prompts to open issues for `REQUIRED` findings
- [ ] README: add `/verify` to slash commands table (remove *(planned)* marker)

---

## ✅ 12. Multi-LLM backend support

**Scope:** Not just Bedrock — also OpenAI, Anthropic direct, Groq, Ollama. Different agents can use different backends and models.

**Implementation plan:**

- [ ] `shared/llm_factory.py` (rename/replace `shared/bedrock.py`) — routes to the right CrewAI LLM class based on `provider`:
  ```python
  def get_llm(provider: str, model: str, **kwargs) -> LLM:
      if provider == "bedrock": return BedrockLLM(model=model, ...)
      if provider == "anthropic": return AnthropicLLM(model=model, ...)
      if provider == "openai": return OpenAILLM(model=model, ...)
      if provider == "groq": return GroqLLM(model=model, ...)
      if provider == "ollama": return OllamaLLM(model=model, ...)
  ```
- [ ] Config: `llm.default.provider`, `llm.default.model`; per-tier overrides `llm.tiers.fast/standard/powerful`; per-agent overrides `llm.agents.security_lead.provider`
  ```yaml
  llm:
    default:
      provider: bedrock
      model: us.anthropic.claude-sonnet-4-6-...
    tiers:
      fast:
        provider: anthropic
        model: claude-haiku-4-5-20251001
      powerful:
        provider: bedrock
        model: us.anthropic.claude-opus-4-8-...
    agents:
      security_lead:
        provider: openai
        model: gpt-4o
  ```
- [ ] `shared/config.py` — add `llm.*` to `_ENV_MAP`; `get_llm_for_tier()` reads the config hierarchy: agent override → tier override → default
- [ ] `pyproject.toml` — add optional extras: `[bedrock]`, `[openai]`, `[groq]`, `[ollama]`; main install only requires `crewai`
- [ ] `shared/bedrock.py` — keep for backward compat; `get_llm_for_tier()` delegates to `llm_factory.py`
- [ ] README: add "LLM backends" section with config example

---

## ✅ 13. Domain modeling

**Scope:** Two modes — design a domain model from requirements, or extract one from existing code. Configurable methodology. Integrates with `/verify` as a drift check. SME input via the existing HumanRelay pattern.

---

### Two modes

**Mode A — `/domain design <KEY>`**
Given a Jira/Linear ticket (or free-text requirement), agents collaboratively build a domain model and write it to `designs/DMD/<service>.md` + a Mermaid diagram.

**Mode B — `/domain extract [path]`**
Engineer scans existing source code (models, DB schema, migration files) and reverse-engineers a domain model. Output goes to the same `designs/DMD/` location. Useful for legacy codebases with no existing documentation.

---

### Methodology (configurable via `domain.methodology` in config or `DOMAIN_METHODOLOGY` env)

| Methodology | Agents involved | Output |
|-------------|----------------|--------|
| `ddd` *(default)* | Architect, Engineer | Bounded contexts, aggregates, entities, value objects, domain events, repositories |
| `event-storming` | Architect (facilitator), Product Owner (business), Engineer (tech), + SME relay | Multi-flow session → per-flow event boards → synthesized domain model |
| `c4` | Architect | C4 context + container diagrams in Mermaid; component-level optional |

Methodology = OKF `.md` file in `knowledge/functions/domain-methodologies/`. New methodologies are added by dropping a file there — no Python changes.

---

### Event storming — multi-flow async session

Event storming runs as a Python-level multi-phase loop (same pattern as DesignFlow):

**Phase 1 — Flow Discovery**
`domain_flow_discovery` task: Architect + Product Owner identify distinct business flows / subdomains (e.g. "User Registration", "Order Fulfilment", "Payment"). Agent batches 3–5 SME questions per HumanRelay call. Output: ordered list of named flows.

**Phase 2 — Per-flow event storming (loop)**
For each flow identified in Phase 1, run `domain_event_storming` task:
- Agent-facilitated event storming: domain events (what happened) → commands (what triggered it) → aggregates (what owns the state) → actors (who issued the command) → policies (when X then Y)
- SME clarification via HumanRelay, batched 3–5 questions per round
- Output per flow: structured event board (events, commands, aggregates, actors, policies)

**Phase 3 — Synthesis**
`domain_synthesis` task: Architect reads all per-flow event boards, produces:
- Bounded context map (which flows share context vs. are separate)
- Aggregate definitions (name, entities, invariants, domain events)
- Ubiquitous language glossary (term → definition → bounded context)
- Mermaid class diagram

All written to `designs/DMD/`.

**Python flow class: `DomainFlow`**
- Phase 1 runs once → extracts flow list
- Phase 2 iterates: one `domain_event_storming` crew run per flow, accumulates outputs
- Phase 3 runs once with all phase-2 outputs as context
- Same state/relay/retry pattern as `DesignFlow`

---

### SME support

For `event-storming`, the flow uses `AskHumanTool` (existing HumanRelay). Agent batches 3–5 questions per call rather than asking one at a time. Format:

```
SME QUESTIONS (round 1 of N):
1. What triggers "OrderPlaced" — user action, external system, or scheduled job?
2. Who can cancel an order — customer only, or also support agents?
3. Is "Payment" a separate bounded context or part of "Order"?
```

User answers inject into the next agent turn. Session is async — user can answer at their own pace.

---

### `/verify` integration

`verify_domain_scan` (new task added to the verify flow):
- Loads domain model from `designs/DMD/`
- Checks code entities/aggregates against model: entity names in code match ubiquitous language, no unmapped entities, bounded context boundaries respected
- Outputs `FINDING [DOMAIN]` / `PASS [DOMAIN]` in the same format as other scan tasks
- Chief review can EXEMPT or mark REQUIRED

---

### Output artifacts

All written to `designs/DMD/`:
```
designs/DMD/
  <service>-domain.md      — full domain model doc (ubiquitous language, bounded contexts, aggregates)
  <service>-diagram.mmd    — Mermaid class/event diagram (renderable in GitHub)
  <service>-glossary.md    — ubiquitous language glossary (term → definition → bounded context)
```

`design_finalize` already commits `designs/` — domain model files ride the same PR flow.

---

### Decisions (resolved)

- **Diagram format:** Mermaid (`.mmd`) — renders in GitHub PRs, no tool install. `domain.diagram_format: plantuml` override deferred to v2.
- **Event storming session:** async, agent-driven in rounds of 3–5 batched SME questions per HumanRelay call.
- **`/domain extract` scope:** one service/path at a time (`[path]` arg, default cwd).
- **Verify drift check:** exact name matching first; LLM semantic check opt-in via `strict` skill.

### Implementation plan

**Methodology docs:**
- [ ] `knowledge/functions/domain-methodologies/ddd.md` — DDD facilitation guide; output format for `.md` + `.mmd`
- [ ] `knowledge/functions/domain-methodologies/event-storming.md` — three-phase guide (flow discovery → per-flow storming → synthesis); SME batch question format; sticky colour conventions
- [ ] `knowledge/functions/domain-methodologies/c4.md` — C4 level 1+2 in Mermaid

**Tasks (5 new OKF files):**
- [ ] `knowledge/tasks/domain_flow_discovery.md` — Phase 1: architect + PO identify named business flows; batch SME questions (3–5 per round); output: ordered flow list
- [ ] `knowledge/tasks/domain_event_storming.md` — Phase 2 (per-flow): events → commands → aggregates → actors → policies; batch SME questions; output: structured per-flow event board
- [ ] `knowledge/tasks/domain_synthesis.md` — Phase 3: reads all per-flow boards; bounded context map + aggregate definitions + ubiquitous language glossary + Mermaid diagram; writes `designs/DMD/`
- [ ] `knowledge/tasks/domain_extract.md` — engineer scans code (models, DB schema, migrations); architect formalises; output in DMD format
- [ ] `knowledge/tasks/verify_domain_scan.md` — exact name drift check: code entities vs `designs/DMD/`; outputs `FINDING [DOMAIN]` / `PASS [DOMAIN]`

**Python:**
- [ ] `code_crew/crew.py` — `build_domain_single_task()` + `_DOMAIN_TASK_AGENTS`; `build_domain_extract_crew()`
- [ ] `code_crew/flow.py` — `DomainFlow`: Phase 1 once → parse flow list → Phase 2 loop per flow → Phase 3 once; same state/relay/retry pattern as `DesignFlow`
- [ ] `code_crew/crew.py` `build_verify_crew()` — add `verify_domain_scan` between `verify_compliance_scan` and `verify_chief_review`
- [ ] `code_crew/repl.py` — `/domain design <KEY>`, `/domain extract [path]`, `/domain` (status)

**Config + docs:**
- [ ] `shared/config.py` — `domain.methodology` → `DOMAIN_METHODOLOGY`; `domain.diagram_format` → `DOMAIN_DIAGRAM_FORMAT`
- [ ] `.config.example.yaml` — add `domain:` section
- [ ] README — `/domain` commands, Domain modeling section, DMD output structure


---

## Order of implementation

Suggested order given dependencies:

1. **Item 2** — OTM/PLOT4ai verification (no new code; doc-only)
2. **Item 12** — Multi-LLM first, because items 5/6/11 may want to use non-Bedrock models
3. **Item 7** — Architecture style config (needed by item 10 `/init` detection)
4. **Item 8** — API standards (function doc + stack docs only)
5. **Item 9** — DB schema management (function doc + stack docs only)
6. **Item 10** — Enhanced `/init` (depends on 7, 8, 9 being in config)
7. **Item 6** — MCP support (infra for item 5 Figma)
8. **Item 5** — UX/Figma flow (depends on MCP for Figma token)
9. **Item 11** — `/verify` flow (largest task; best done after 7-9 so scan tasks can reference arch/api/db standards)
