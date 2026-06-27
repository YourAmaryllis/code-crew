"""
Ops crew: virtual infrastructure and operations team for SDLC phases 12, 16, 20-22.

All agent instructions and task descriptions are loaded from OKF markdown files
in knowledge/agents/ and knowledge/tasks/. No prompts are hardcoded here.
"""

from pathlib import Path

from crewai import Agent, Crew, Process, Task

from shared.bedrock import get_fast_llm, get_llm
from shared.okf_loader import load_bundle_agents, load_bundle_tasks
from shared.tools import SOPReaderTool

_KNOWLEDGE = Path(__file__).parent / "knowledge"

sop_reader = SOPReaderTool()


def build_crew(infra_input: dict) -> Crew:
    """
    Build the ops crew for an infrastructure work item.

    infra_input keys:
      jira_key        - e.g. "PROJ-NNN"
      description     - what infrastructure work is needed
      services        - list of service names affected (e.g. ["portal", "attestation"])
      environments    - list of target envs (e.g. ["dev", "staging"])
      sprint_goal     - one-sentence goal from the sprint
    """
    agents_dir = _KNOWLEDGE / "agents"
    tasks_dir = _KNOWLEDGE / "tasks"

    ac = load_bundle_agents(agents_dir)
    tc = load_bundle_tasks(tasks_dir)

    # --- Agents ---

    ops_lead = Agent(
        role=ac["ops_lead"].role,
        goal=ac["ops_lead"].goal,
        backstory=ac["ops_lead"].backstory,
        tools=[sop_reader],
        llm=get_fast_llm(),
        verbose=True,
    )

    terraform_engineer = Agent(
        role=ac["terraform_engineer"].role,
        goal=ac["terraform_engineer"].goal,
        backstory=ac["terraform_engineer"].backstory,
        tools=[sop_reader],
        llm=get_llm(),
        verbose=True,
    )

    cicd_engineer = Agent(
        role=ac["cicd_engineer"].role,
        goal=ac["cicd_engineer"].goal,
        backstory=ac["cicd_engineer"].backstory,
        tools=[sop_reader],
        llm=get_llm(),
        verbose=True,
    )

    monitoring_engineer = Agent(
        role=ac["monitoring_engineer"].role,
        goal=ac["monitoring_engineer"].goal,
        backstory=ac["monitoring_engineer"].backstory,
        tools=[sop_reader],
        llm=get_llm(),
        verbose=True,
    )

    release_manager = Agent(
        role=ac["release_manager"].role,
        goal=ac["release_manager"].goal,
        backstory=ac["release_manager"].backstory,
        tools=[sop_reader],
        llm=get_fast_llm(),
        verbose=True,
    )

    # --- Tasks ---

    context_header = _format_context(infra_input)

    env_plan = Task(
        description=f"{context_header}\n\n{tc['environment_plan'].description}",
        expected_output=tc["environment_plan"].expected_output,
        agent=ops_lead,
    )

    tf_write = Task(
        description=f"{context_header}\n\n{tc['terraform_write'].description}",
        expected_output=tc["terraform_write"].expected_output,
        agent=terraform_engineer,
        context=[env_plan],
    )

    cicd_config = Task(
        description=f"{context_header}\n\n{tc['cicd_config'].description}",
        expected_output=tc["cicd_config"].expected_output,
        agent=cicd_engineer,
        context=[env_plan, tf_write],
    )

    monitoring = Task(
        description=f"{context_header}\n\n{tc['monitoring_setup'].description}",
        expected_output=tc["monitoring_setup"].expected_output,
        agent=monitoring_engineer,
        context=[tf_write],
    )

    release = Task(
        description=f"{context_header}\n\n{tc['release_plan'].description}",
        expected_output=tc["release_plan"].expected_output,
        agent=release_manager,
        context=[env_plan, monitoring],
    )

    return Crew(
        agents=[ops_lead, terraform_engineer, cicd_engineer, monitoring_engineer, release_manager],
        tasks=[env_plan, tf_write, cicd_config, monitoring, release],
        process=Process.sequential,
        verbose=True,
    )


def _format_context(infra_input: dict) -> str:
    services = ", ".join(infra_input.get("services", [])) or "not specified"
    environments = ", ".join(infra_input.get("environments", ["dev", "staging"]))
    return (
        f"## Infrastructure context\n\n"
        f"**Jira key**: {infra_input.get('jira_key', 'UNKNOWN')}\n"
        f"**Sprint goal**: {infra_input.get('sprint_goal', '')}\n"
        f"**Description**: {infra_input.get('description', '')}\n"
        f"**Services affected**: {services}\n"
        f"**Target environments**: {environments}"
    )
