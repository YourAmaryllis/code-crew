"""
CrewAI tool: run BDD integration tests in the current project directory.

Wraps `go test ./integration/...` with godog tags and interface flags.
Always read-only against the test environment — never touches production.
"""

import subprocess
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class BDDRunnerInput(BaseModel):
    tags: str = Field(
        default="",
        description=(
            "Godog tag expression to filter scenarios. Examples: "
            "'@LOOPLAT-72', '@dataset and not @wip', '@smoke'. "
            "Leave empty to run all scenarios."
        ),
    )
    interface: str = Field(
        default="api",
        description="Test interface mode: 'api' (HTTP), 'ui' (Playwright), or 'cli'. Default: api.",
    )
    feature: str = Field(
        default="",
        description=(
            "Specific feature file stem to run (without .feature extension). "
            "Example: 'dataset_registration'. Leave empty to run all features."
        ),
    )
    timeout: int = Field(
        default=300,
        description="Timeout in seconds. Default: 300.",
    )


class BDDTestRunnerTool(BaseTool):
    name: str = "bdd_runner"
    description: str = (
        "Run BDD integration tests in the project using godog. "
        "Filter by ticket tag (e.g. '@PROJ-72'), interface mode (api/ui/cli), "
        "or specific feature file. Returns test output with pass/fail counts. "
        "Use this after writing or updating .feature files to verify scenarios pass."
    )
    args_schema: type[BaseModel] = BDDRunnerInput
    code_path: str = ""  # set by Flow per worktree; empty = use cwd

    def _root(self) -> Path:
        return Path(self.code_path).resolve() if self.code_path else Path.cwd()

    def _run(
        self,
        tags: str = "",
        interface: str = "api",
        feature: str = "",
        timeout: int = 300,
    ) -> str:
        integration_dir = self._root() / "integration"

        if not integration_dir.exists():
            return f"ERROR: integration directory not found at {integration_dir}"

        cmd_parts = ["go", "test", "-v", "-timeout", f"{timeout}s"]

        if feature:
            cmd_parts += [f"./features/{feature}_test.go"]
        else:
            cmd_parts.append("./...")

        godog_args = f"-interface={interface}"
        if tags:
            godog_args += f" -godog.tags='{tags}'"

        cmd_parts += ["-args", godog_args]
        command = " ".join(cmd_parts)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(integration_dir),
                capture_output=True,
                text=True,
                timeout=timeout + 30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            if result.returncode != 0:
                output = f"TESTS FAILED (exit {result.returncode})\n{output}"
            else:
                output = f"TESTS PASSED\n{output}"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"ERROR: BDD tests timed out after {timeout} seconds"
        except Exception as e:
            return f"ERROR: {e}"
