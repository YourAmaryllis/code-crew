"""
Entry point for the ops crew.

Usage:
  python -m ops.main --jira PROJ-NNN \
      --description "Add CloudWatch alarms for attestation service" \
      --service attestation --service portal \
      --env dev --env staging \
      --sprint-goal "Observability for attestation"
"""

from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


@click.command()
@click.option("--jira", required=True, help="Jira issue key (e.g. PROJ-NNN)")
@click.option("--description", required=True, help="What infrastructure work is needed")
@click.option("--service", multiple=True, help="Service name(s) affected (repeat for multiple)")
@click.option("--env", multiple=True, default=["dev", "staging"], help="Target environment(s)")
@click.option("--sprint-goal", default="", help="One-sentence sprint goal")
@click.option("--output", default=None, help="Write crew output to this file path")
def run(jira, description, service, env, sprint_goal, output):
    """Run the ops crew for an infrastructure work item."""
    from ops.crew import build_crew  # noqa: PLC0415

    infra_input = {
        "jira_key": jira,
        "description": description,
        "services": list(service),
        "environments": list(env),
        "sprint_goal": sprint_goal,
    }

    crew = build_crew(infra_input)
    result = crew.kickoff(inputs=infra_input)

    output_text = str(result)
    if output:
        Path(output).write_text(output_text, encoding="utf-8")
        click.echo(f"Output written to {output}")
    else:
        click.echo(output_text)


if __name__ == "__main__":
    run()
