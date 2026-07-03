"""
Entry point for the code crew.

Usage:
  code-crew run --jira PROJ-NNN
  code-crew sprint --sprint "Sprint 5"
  code-crew sprint --jira PROJ-NNN PROJ-NNN PROJ-NNN
  code-crew memory add "note" --category env
  code-crew memory list

Config is loaded from ~/.code-crew/config.yaml (see .config.example.yaml for format).
"""

import click

from shared.config import load_yaml_config
from shared.home import CONFIG_YAML, ensure_home

ensure_home()
if CONFIG_YAML.exists():
    load_yaml_config(CONFIG_YAML, override=False)


@click.group()
def cli():
    """Virtual code crew — run sprints and manage memory."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ticket(jira_key: str, sprint_name: str = "", extra_adds: list[str] | None = None) -> str:
    """Fetch, plan, and run the crew for a single ticket. Returns output text."""
    from code_crew.crew import build_crew
    from shared.jira_client import fetch
    from shared.user_memory import UserMemory

    ticket = fetch(jira_key)

    memory = UserMemory()
    terms = [jira_key] + ticket.acceptance_criteria + ticket.sprint_goal.split()
    user_context = memory.format_for_context(jira_key=jira_key, terms=terms)

    sprint_input = {
        "jira_key": jira_key,
        "story": ticket.story,
        "acceptance_criteria": ticket.acceptance_criteria,
        "sprint_goal": ticket.sprint_goal,
        "figma_url": ticket.figma_url,
        "html_design_ref": ticket.html_design_ref,
        "add_refs": ticket.add_refs + (extra_adds or []),
        "comment_context": ticket.comment_context,
        "sprint_name": sprint_name,
        "user_context": user_context,
    }

    crew = build_crew(sprint_input)
    result = crew.kickoff(inputs=sprint_input)
    return str(result)


def _save_output(text: str, sprint_name: str, ticket_key: str) -> Path:
    from shared.home import output_path
    path = output_path(sprint_name, ticket_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Run (single ticket)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--jira", required=True, help="Jira issue key (e.g. PROJ-NNN)")
@click.option("--story", default="", help="Override extracted user story")
@click.option("--ac", multiple=True, help="Override extracted ACs (repeat for multiple)")
@click.option("--sprint-goal", default="", help="Override extracted sprint goal")
@click.option("--figma", default="", help="Override extracted Figma URL")
@click.option("--add", multiple=True, help="Extra ADD/ADR names to include")
@click.option("--output", default=None, help="Write crew output to this file path")
def run(jira, story, ac, sprint_goal, figma, add, output):
    """Run the code crew for a single ticket.

    Story, ACs, sprint goal, Figma URL, and ADD refs are extracted from the
    Jira ticket automatically. Pass flags above to override any extracted field.
    """
    import sys

    from code_crew.crew import build_crew
    from shared.jira_client import MissingACError, MissingStoryError, fetch
    from shared.user_memory import UserMemory

    click.echo(f"Fetching {jira} from Jira...")
    try:
        ticket = fetch(jira)
    except (MissingStoryError, MissingACError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    resolved_story = story or ticket.story
    resolved_acs = list(ac) if ac else ticket.acceptance_criteria
    resolved_goal = sprint_goal or ticket.sprint_goal
    resolved_figma = figma or ticket.figma_url

    click.echo(f"  Story: {resolved_story[:80]}...")
    click.echo(f"  ACs:   {len(resolved_acs)} items")
    click.echo(f"  Goal:  {resolved_goal}")

    memory = UserMemory()
    terms = [jira] + resolved_acs + resolved_goal.split()
    user_context = memory.format_for_context(jira_key=jira, terms=terms)

    sprint_input = {
        "jira_key": jira,
        "story": resolved_story,
        "acceptance_criteria": resolved_acs,
        "sprint_goal": resolved_goal,
        "figma_url": resolved_figma,
        "html_design_ref": ticket.html_design_ref,
        "add_refs": list(add) + ticket.add_refs,
        "comment_context": ticket.comment_context,
        "user_context": user_context,
    }

    crew = build_crew(sprint_input)
    result = crew.kickoff(inputs=sprint_input)
    output_text = str(result)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        click.echo(f"Output written to {output}")
    else:
        click.echo(output_text)


# ---------------------------------------------------------------------------
# Sprint (all tickets in a sprint)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--sprint", "sprint_name", default="", help="Sprint name (default: active sprint). Requires JIRA_URL/JIRA_USER/JIRA_TOKEN.")
@click.option("--jira", "jira_keys", multiple=True, help="Ticket keys to include (alternative to --sprint).")
@click.option("--output-dir", default=None, help="Directory for per-ticket output files (default: ~/.code-crew/outputs/<sprint>/).")
@click.option("--dry-run", is_flag=True, help="Show sprint plan without running any crews.")
def sprint(sprint_name, jira_keys, output_dir, dry_run):
    """Run the code crew for all tickets in a sprint, in dependency order.

    \b
    Examples:
      # Fetch active sprint tickets automatically (needs JIRA_URL/USER/TOKEN):
      code-crew sprint
      code-crew sprint --sprint "Sprint 5"

      # Specify tickets explicitly:
      code-crew sprint --jira PROJ-NNN --jira PROJ-NNN --jira PROJ-NNN

      # Preview the plan without running:
      code-crew sprint --jira PROJ-NNN --jira PROJ-NNN --dry-run
    """
    import os
    import sys

    from shared.jira_client import MissingACError, MissingStoryError
    from shared.sprint_planner import (
        fetch_sprint_tickets,
        list_sprint_ticket_keys,
        plan_execution_order,
    )

    effective_sprint = sprint_name or "active-sprint"

    # --- Step 1: Get ticket keys ---
    if jira_keys:
        keys = list(jira_keys)
    else:
        click.echo(f"Listing tickets for sprint: {sprint_name or 'active'}...")
        try:
            keys = list_sprint_ticket_keys(
                project=os.environ.get("JIRA_PROJECT", ""),
                sprint_name=sprint_name,
            )
        except RuntimeError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)

    if not keys:
        click.echo("No tickets found.")
        return

    click.echo(f"Found {len(keys)} tickets: {', '.join(keys)}")

    # --- Step 2: Fetch and extract each ticket ---
    click.echo("\nFetching ticket details...")
    tickets, skipped = fetch_sprint_tickets(keys)

    if skipped:
        click.echo("\nSkipped (missing story/ACs — update Jira before running crew):")
        for s in skipped:
            click.echo(f"  ❌ {s['key']}: {s['reason'][:120]}")

    if not tickets:
        click.echo("\nNo actionable tickets found.", err=True)
        sys.exit(1)

    # --- Step 3: Sprint planning — dependency analysis ---
    click.echo(f"\nPlanning execution order for {len(tickets)} tickets...")
    waves = plan_execution_order(tickets)

    click.echo("\nExecution plan:")
    for i, wave in enumerate(waves, 1):
        keys_str = ", ".join(t.key for t in wave)
        label = "(parallel)" if len(wave) > 1 else ""
        click.echo(f"  Wave {i}: {keys_str} {label}")

    if dry_run:
        click.echo("\n--dry-run: stopping here.")
        return

    # --- Step 4: Execute each ticket in wave order ---
    results: dict[str, str] = {}
    failed: list[str] = []

    click.echo("")
    for wave_idx, wave in enumerate(waves, 1):
        click.echo(f"── Wave {wave_idx} {'─' * 50}")
        for ticket in wave:
            click.echo(f"\n▶ {ticket.key}: {ticket.summary}")
            try:
                output_text = _run_ticket(ticket.key, sprint_name=effective_sprint)
                results[ticket.key] = output_text

                out_path = (
                    Path(output_dir) / f"{ticket.key}.md"
                    if output_dir
                    else _save_output(output_text, effective_sprint, ticket.key)
                )
                click.echo(f"  ✅ Done → {out_path}")

            except Exception as exc:
                failed.append(ticket.key)
                click.echo(f"  ❌ Failed: {exc}", err=True)

    # --- Summary ---
    click.echo(f"\n{'─' * 60}")
    click.echo(f"Sprint run complete.")
    click.echo(f"  ✅ Completed: {len(results)} tickets")
    if skipped:
        click.echo(f"  ⏭  Skipped:   {len(skipped)} tickets (missing story/ACs)")
    if failed:
        click.echo(f"  ❌ Failed:    {len(failed)} tickets: {', '.join(failed)}")

    outputs_dir = Path(output_dir) if output_dir else _save_output("", effective_sprint, "_placeholder").parent
    click.echo(f"\nOutputs: {outputs_dir}")


# ---------------------------------------------------------------------------
# Memory subgroup
# ---------------------------------------------------------------------------

@cli.group()
def memory():
    """Manage user context that the crew picks up at run time."""


@memory.command("add")
@click.argument("content")
@click.option(
    "--category", "-c",
    default="notes",
    type=click.Choice(["decisions", "blockers", "env", "jira", "security", "notes", "always"]),
    help="Category: 'always' = injected every run; others = keyword-matched.",
)
@click.option("--tag", "-t", multiple=True, help="Jira key or other tag. Repeat for multiple.")
def memory_add(content, category, tag):
    """Add a context entry to memory.

    \b
    Examples:
      code-crew memory add "staging DB migrated to RDS" --category env
      code-crew memory add "PROJ-NNN blocked by auth refactor" --category blockers --tag PROJ-NNN
      code-crew memory add "use pgx v5 for all new DB code" --category decisions
    """
    from shared.user_memory import UserMemory
    mem = UserMemory()
    entry = mem.add(content, category=category, tags=list(tag))
    click.echo(f"Added [{entry.id}] ({entry.category}): {entry.content}")


@memory.command("list")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--tag", "-t", default=None, help="Filter by tag.")
def memory_list(category, tag):
    """List memory entries."""
    from shared.user_memory import UserMemory
    entries = UserMemory().list(category=category, tag=tag)
    if not entries:
        click.echo("No entries found.")
        return
    for e in entries:
        click.echo(str(e))


@memory.command("remove")
@click.argument("entry_id")
def memory_remove(entry_id):
    """Remove a memory entry by ID."""
    from shared.user_memory import UserMemory
    if UserMemory().remove(entry_id):
        click.echo(f"Removed entry {entry_id}.")
    else:
        click.echo(f"Entry '{entry_id}' not found.", err=True)


@memory.command("clear")
@click.option("--category", "-c", default=None, help="Clear only this category.")
@click.confirmation_option(prompt="This will delete memory entries. Continue?")
def memory_clear(category):
    """Clear all (or one category of) memory entries."""
    n = UserMemory().clear(category=category)
    click.echo(f"Cleared {n} entries.")


@memory.command("show")
@click.option("--jira", default="", help="Jira key to simulate context recall for.")
def memory_show(jira):
    """Preview what memory the crew would see for a given Jira key."""
    from shared.user_memory import UserMemory
    ctx = UserMemory().format_for_context(jira_key=jira)
    click.echo(ctx if ctx else "No relevant memory entries found.")


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", default="", required=False)
def explore(path):
    """Scan the project, detect stacks and build/test commands, identify OTM scopes.

    \b
    Examples:
      code-crew explore            # scan cwd
      code-crew explore ../myapp   # scan another directory
    """
    from rich.console import Console
    from code_crew.repl import _run_explore
    _run_explore(path, Console())


# ---------------------------------------------------------------------------
# Threat
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("target", default="", required=False)
def threat(target):
    """Generate or refresh OTM threat models for the current project.

    Reads the component inventory saved by 'explore'. Pass an optional project
    id to target a single scope; without one, generates all identified projects.

    \b
    Examples:
      code-crew threat             # all projects in cwd
      code-crew threat portal      # only the portal scope
    """
    from rich.console import Console
    from code_crew.repl import _run_threat
    _run_threat(target, Console())


if __name__ == "__main__":
    cli()
