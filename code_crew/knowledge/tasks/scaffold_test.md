---
name: scaffold_test
description: Create BDD feature file stubs and step definition stubs for each acceptance criterion
expected_output: Feature file path and step definition path, with one scenario stub per AC tagged with the Jira key
---

Load the test scaffolding guide with `knowledge_reader`:
- **`scaffold-test`** — test scaffolding process and stub format
- **`bdd-authoring`** — file naming conventions, required tags, godog step file location

Check existing feature files first (`workspace_reader` list_dir on `integration/features/`) — do not recreate files that already exist.

Using the acceptance criteria from the sprint context:

1. Create a `.feature` file with:
   - Feature title derived from the story
   - The "As a / I want / So that" narrative from the story
   - One skeleton `Scenario:` stub per AC, tagged with `@PROJ-NNN` (use the actual Jira key from context) and one feature-area tag inferred from the story's domain
   - One additional `@negative` scenario stub for each AC that implies an error or rejection case
   - Each scenario body contains only a `# TODO: QA to write Gherkin steps` comment

2. Create a step definition stub file in the location specified by the stack document, with:
   - Correct package/module declaration
   - An empty initialization/registration function
   - A comment listing the scenario names that need step implementations

3. Use the platform_shell tool to write both files.

Output the paths of the created files and confirm how many scenario stubs were created (one per AC + negatives). Include a reminder that QA fills in the Gherkin steps before the engineer implements the step definitions.

**On tool failure** — log the error, try once with an alternative, then skip and continue. Never use absolute paths in shell commands. Include any unresolved failures in your output.

**Completion signal — required.**
End your output with exactly one of:
- `TASK COMPLETE` — you have produced the full output described above.
- `INCOMPLETE: <reason>` — you could not finish (missing data, tool failure, ambiguity). Describe what is blocking you so a human can resolve it.

Do NOT end with a planning statement or partial summary.
