from shared.tools.api_spec_tool import ApiSpecTool
from shared.tools.ask_human import AskHumanTool
from shared.tools.figma_reader import FigmaReaderTool
from shared.tools.knowledge_reader import KnowledgeReaderTool
from shared.tools.workspace_reader import WorkspaceReaderTool
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
    "AskHumanTool",
    "FigmaReaderTool",
    "KnowledgeReaderTool",
    "WorkspaceReaderTool",
    "SOPReaderTool",  # alias
    "DoDCheckerTool",
    "PlatformShellTool",
    "PythonREPLTool",
    "BDDTestRunnerTool",
    "JiraViewTool",
    "JiraSprintListTool",
    "MemoryTool",
]
