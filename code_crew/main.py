"""
Entry point for the code crew.

Usage:
  code-crew run --jira LOOPLAT-72
  code-crew run --jira LOOPLAT-72 --sprint-goal "Custom goal override"
  code-crew memory add "staging DB migrated to RDS" --category env
  code-crew memory list
  code-crew memory remove <id>

Story, ACs, sprint goal, Figma URL, and ADD refs are extracted from the Jira
ticket automatically. All flags below are optional overrides.
"""

from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


@click.group()
def cli():
    """YourAmaryllis virtual code crew — run sprints and manage memory."""


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--jira", required=True, help="Jira issue key (e.g. LOOPLAT-72)")
@click.option("--story", default="", help="Override extracted user story")
@click.option("--ac", multiple=True, help="Override extracted ACs (repeat for multiple)")
@click.option("--sprint-goal", default="", help="Override extracted sprint goal")
@click.option("--figma", default="", help="Override extracted Figma URL")
@click.option("--add", multiple=True, help="Extra ADD/ADR names to include (repeat for multiple)")
@click.option("--output", default=None, help="Write crew output to this file path")
def run(jira, story, ac, sprint_goal, figma, add, output):
    """Run the code crew for a single sprint story.

    Story, ACs, sprint goal, Figma URL, and ADD refs are extracted from the
    Jira ticket automatically. Pass flags above to override any extracted field.
    """
    import sys

    from code_crew.crew import build_crew  # noqa: PLC0415 — import after env load
    from shared.jira_client import MissingACError, MissingStoryError, fetch
    from shared.user_memory import UserMemory

    # --- Fetch and extract ticket fields via LLM ---
    click.echo(f"Fetching {jira} from Jira...")
    try:
        ticket = fetch(jira)
    except (MissingStoryError, MissingACError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    # CLI overrides win over extracted values
    resolved_story = story or ticket.story
    resolved_acs = list(ac) if ac else ticket.acceptance_criteria
    resolved_goal = sprint_goal or ticket.sprint_goal
    resolved_figma = figma or ticket.figma_url
    resolved_html_design = ticket.html_design_ref
    resolved_adds = list(add) + ticket.add_refs  # merge: CLI extras + ticket refs

    click.echo(f"  Story: {resolved_story[:80]}...")
    click.echo(f"  ACs:   {len(resolved_acs)} items")
    click.echo(f"  Goal:  {resolved_goal}")

    # Recall relevant user context
    memory = UserMemory()
    terms = [jira] + resolved_acs + resolved_goal.split()
    user_context = memory.format_for_context(jira_key=jira, terms=terms)

    sprint_input = {
        "jira_key": jira,
        "story": resolved_story,
        "acceptance_criteria": resolved_acs,
        "sprint_goal": resolved_goal,
        "figma_url": resolved_figma,
        "html_design_ref": resolved_html_design,
        "add_refs": resolved_adds,
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
    help=(
        "Category: 'always' = injected every run; "
        "'jira' = tag with --tag to link to a ticket; "
        "others = keyword-matched."
    ),
)
@click.option("--tag", "-t", multiple=True, help="Jira key or other tag (e.g. LOOPLAT-72). Repeat for multiple.")
def memory_add(content, category, tag):
    """Add a context entry to memory.

    \b
    Examples:
      code-crew memory add "staging DB migrated to RDS on 2026-06-17" --category env
      code-crew memory add "LOOPLAT-72 blocked by LOOPLAT-50 auth refactor" --category blockers --tag LOOPLAT-72
      code-crew memory add "use pgx v5 for all new DB code" --category decisions
      code-crew memory add "AWS profile for youramaryllis is 'youramaryllis-dev'" --category always
    """
    from shared.user_memory import UserMemory
    mem = UserMemory()
    entry = mem.add(content, category=category, tags=list(tag))
    click.echo(f"Added [{entry.id}] ({entry.category}): {entry.content}")


@memory.command("list")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--tag", "-t", default=None, help="Filter by tag (e.g. LOOPLAT-72).")
def memory_list(category, tag):
    """List memory entries."""
    from shared.user_memory import UserMemory
    mem = UserMemory()
    entries = mem.list(category=category, tag=tag)
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
    mem = UserMemory()
    if mem.remove(entry_id):
        click.echo(f"Removed entry {entry_id}.")
    else:
        click.echo(f"Entry '{entry_id}' not found.", err=True)


@memory.command("clear")
@click.option("--category", "-c", default=None, help="Clear only this category. Omit to clear all.")
@click.confirmation_option(prompt="This will delete memory entries. Continue?")
def memory_clear(category):
    """Clear all (or one category of) memory entries."""
    from shared.user_memory import UserMemory
    mem = UserMemory()
    n = mem.clear(category=category)
    click.echo(f"Cleared {n} entries.")


@memory.command("show")
@click.option("--jira", default="", help="Jira key to simulate context recall for.")
def memory_show(jira):
    """Preview what memory the crew would see for a given Jira key."""
    from shared.user_memory import UserMemory
    mem = UserMemory()
    ctx = mem.format_for_context(jira_key=jira)
    if ctx:
        click.echo(ctx)
    else:
        click.echo("No relevant memory entries found.")


if __name__ == "__main__":
    cli()
