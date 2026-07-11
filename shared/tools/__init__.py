from shared.tools.api_spec_tool import ApiSpecTool
from shared.tools.async_job import AsyncJobTool, CiStatusTool  # CiStatusTool is a backward-compat alias
from shared.tools.ask_human import AskHumanTool
from shared.tools.figma_reader import FigmaReaderTool
from shared.tools.knowledge_reader import KnowledgeReaderTool
from shared.tools.stack_reader import StackReaderTool
from shared.tools.workspace_reader import WorkspaceReaderTool
from shared.tools.code_index import CodeIndexTool
from shared.tools.dod_checker import DoDCheckerTool
from shared.tools.platform_shell import PlatformShellTool
from shared.tools.python_repl import PythonREPLTool
from shared.tools.bdd_runner import BDDTestRunnerTool
from shared.tools.jira_tool import JiraViewTool, JiraSprintListTool
from shared.tools.memory_tool import MemoryTool

# Backward-compat alias — ops/crew.py still imports SOPReaderTool
SOPReaderTool = KnowledgeReaderTool

__all__ = [
    "ApiSpecTool",
    "AsyncJobTool",
    "CiStatusTool",  # backward-compat alias
    "AskHumanTool",
    "FigmaReaderTool",
    "KnowledgeReaderTool",  # kept for backward-compat; not in _make_tools()
    "StackReaderTool",
    "WorkspaceReaderTool",
    "CodeIndexTool",
    "SOPReaderTool",  # alias
    "DoDCheckerTool",
    "PlatformShellTool",
    "PythonREPLTool",
    "BDDTestRunnerTool",
    "JiraViewTool",
    "JiraSprintListTool",
    "MemoryTool",
]
