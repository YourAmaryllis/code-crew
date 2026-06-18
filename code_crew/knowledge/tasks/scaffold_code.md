---
name: scaffold_code
description: Create the directory structure and code stubs for the user story
expected_output: Manifest of created files and directories with their purpose
---

Read the `scaffold-code` document using the knowledge_reader tool to understand the scaffolding process and structure.

Then read the relevant stack document(s) (e.g. `go-backend`, `typescript-react`, `python`, `terraform-aws`) to determine the exact directory layout and stub file format for this project's tech stack.

Using the acceptance criteria and story context:

1. Determine whether this story requires: a new service, a new feature within an existing service, a new UI component, or a combination.

2. If the architect's review (from context) recommended a specific service name, module name, or structural pattern — follow it exactly.

3. Use the platform_shell tool to create the required directories and stub files. Stubs must have:
   - Correct package declarations (Go) / module exports (TypeScript) / class definitions (Python)
   - Empty function signatures named after the domain concept from the story
   - No implemented logic — stubs only
   - Import statements for the interfaces/types they will depend on (as TODOs if not yet defined)

4. Skip scaffolding if the story is a bug fix, a config change, or affects only a single existing file.

Output a manifest listing each created path and its purpose (e.g. "domain entity stub", "repository interface", "HTTP handler stub"). Include a note on which parts the backend engineer should implement first.
