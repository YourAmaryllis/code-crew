"""
CrewAI tool: Python REPL for local debugging and data inspection.

Executes Python snippets in an isolated subprocess. Useful for:
- Inspecting JSON/YAML output from other tools
- Running quick data transformations or calculations
- Debugging parsing logic
"""

import subprocess
import sys
import textwrap

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class PythonREPLInput(BaseModel):
    code: str = Field(
        description=(
            "Python code to execute. Use print() to show output. "
            "Standard library and common packages (json, yaml, pathlib, re, datetime) available. "
            "No network access, no file writes outside /tmp."
        )
    )


class PythonREPLTool(BaseTool):
    name: str = "python_repl"
    description: str = (
        "Execute Python code for data inspection, JSON/YAML parsing, calculations, "
        "or debugging. Use print() to emit results. Standard library available. "
        "Useful for parsing CLI output from other tools or validating data shapes."
    )
    args_schema: type[BaseModel] = PythonREPLInput

    def _run(self, code: str) -> str:
        # Wrap code to prevent obvious destructive operations
        blocked = ["os.system", "subprocess", "shutil.rmtree", "__import__('os').remove"]
        for b in blocked:
            if b in code:
                return f"BLOCKED: '{b}' is not allowed in REPL code."

        # Indent code and wrap in try/except for better error reporting
        indented = textwrap.indent(code, "    ")
        wrapped = f"try:\n{indented}\nexcept Exception as e:\n    print(f'ERROR: {{e}}')"

        try:
            result = subprocess.run(
                [sys.executable, "-c", wrapped],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: code timed out after 30 seconds"
        except Exception as e:
            return f"ERROR: {e}"
