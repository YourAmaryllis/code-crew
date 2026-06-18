from shared.tools.knowledge_reader import KnowledgeReaderTool
from shared.tools.dod_checker import DoDCheckerTool
from shared.tools.platform_shell import PlatformShellTool
from shared.tools.python_repl import PythonREPLTool
from shared.tools.bdd_runner import BDDTestRunnerTool
from shared.tools.jira_tool import JiraViewTool, JiraSprintListTool
from shared.tools.memory_tool import MemoryTool

# Backward-compat alias — ops/crew.py still imports SOPReaderTool
SOPReaderTool = KnowledgeReaderTool

__all__ = [
    "KnowledgeReaderTool",
    "SOPReaderTool",  # alias
    "DoDCheckerTool",
    "PlatformShellTool",
    "PythonREPLTool",
    "BDDTestRunnerTool",
    "JiraViewTool",
    "JiraSprintListTool",
    "MemoryTool",
]
