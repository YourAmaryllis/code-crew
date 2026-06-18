"""Tests for shared.issue_tracker: routing, Linear parsing, Jira delegation."""

import json
from unittest.mock import MagicMock, patch

import pytest

from shared.issue_tracker import (
    IssueTrackerClient,
    Ticket,
    TrackerError,
    MissingFieldError,
    _linear_to_ticket,
    _parse_story_and_acs,
)


# ---------------------------------------------------------------------------
# _parse_story_and_acs
# ---------------------------------------------------------------------------

def test_parse_story():
    desc = "As a user, I want to log in so that I can access my dashboard."
    story, acs = _parse_story_and_acs(desc)
    assert story.startswith("As a user")


def test_parse_acs():
    desc = (
        "As a user, I want to log in so that I can access my dashboard.\n\n"
        "Acceptance Criteria:\n"
        "- Login form renders\n"
        "- Valid credentials succeed\n"
        "- Invalid credentials show error\n"
    )
    _, acs = _parse_story_and_acs(desc)
    assert len(acs) == 3
    assert "Login form renders" in acs


def test_parse_empty_description():
    story, acs = _parse_story_and_acs("")
    assert story == ""
    assert acs == []


# ---------------------------------------------------------------------------
# _linear_to_ticket
# ---------------------------------------------------------------------------

def test_linear_to_ticket():
    data = {
        "identifier": "ENG-42",
        "title": "Add login page",
        "state": {"name": "In Progress"},
        "description": (
            "As a user, I want to log in so that I can see my data.\n\n"
            "Acceptance Criteria:\n- Login form renders\n"
        ),
    }
    ticket = _linear_to_ticket(data)
    assert ticket.key == "ENG-42"
    assert ticket.summary == "Add login page"
    assert ticket.status == "In Progress"
    assert "log in" in ticket.story
    assert "Login form renders" in ticket.acceptance_criteria


# ---------------------------------------------------------------------------
# IssueTrackerClient routing
# ---------------------------------------------------------------------------

def test_routes_to_jira_by_default(monkeypatch):
    monkeypatch.delenv("ISSUE_TRACKER", raising=False)
    client = IssueTrackerClient()
    assert client.tracker == "jira"


def test_routes_to_linear(monkeypatch):
    monkeypatch.setenv("ISSUE_TRACKER", "linear")
    client = IssueTrackerClient()
    assert client.tracker == "linear"


def test_jira_get_ticket_delegates():
    from shared.jira_client import JiraTicket
    fake_ticket = JiraTicket(
        key="PROJ-1", summary="Test", status="Open",
        story="As a user, I want X so that Y.",
        acceptance_criteria=["AC1"], sprint_goal="Goal",
        figma_url="", html_design_ref="", add_refs=[], comment_context="",
    )
    with patch("shared.issue_tracker._jira_fetch", return_value=fake_ticket):
        client = IssueTrackerClient()
        result = client.get_ticket("PROJ-1")
    assert result.key == "PROJ-1"
    assert isinstance(result, Ticket)


def test_jira_get_raises_missing_field():
    from shared.jira_client import MissingStoryError
    with patch("shared.issue_tracker._jira_fetch", side_effect=MissingStoryError("no story")):
        client = IssueTrackerClient()
        with pytest.raises(MissingFieldError):
            client.get_ticket("PROJ-1")


def test_linear_get_requires_cli():
    import subprocess
    with patch.dict("os.environ", {"ISSUE_TRACKER": "linear"}):
        client = IssueTrackerClient()
        with patch("subprocess.run") as mock_run:
            # which linear → not found
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            with pytest.raises(TrackerError, match="linear CLI not found"):
                client.get_ticket("ENG-1")


def test_linear_get_ticket():
    data = {
        "identifier": "ENG-5",
        "title": "New feature",
        "state": {"name": "Todo"},
        "description": "As a user, I want X so that Y.\n\nAcceptance Criteria:\n- AC1\n",
    }
    with patch.dict("os.environ", {"ISSUE_TRACKER": "linear"}):
        client = IssueTrackerClient()
        with patch("subprocess.run") as mock_run:
            # which linear → found
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="/usr/local/bin/linear"),
                MagicMock(returncode=0, stdout=json.dumps(data)),
            ]
            ticket = client.get_ticket("ENG-5")
    assert ticket.key == "ENG-5"
    assert "AC1" in ticket.acceptance_criteria
