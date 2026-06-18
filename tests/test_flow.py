"""Tests for code_crew.flow: TicketState, ReviewResult, TicketFlow retry logic."""

import threading
from unittest.mock import MagicMock, patch, call

import pytest

from code_crew.flow import ReviewResult, TicketFlow, TicketState


# ---------------------------------------------------------------------------
# ReviewResult parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("output,expected_pass", [
    ("APPROVED: all checks pass", True),
    ("Code review PASSED", True),
    ("LGTM — looks good", True),
    ("Review complete. No issues.", True),
    ("REJECTED: missing error handling", False),
    ("Code review FAILED: layer violation", False),
    ("REJECTED", False),
    ("", False),
])
def test_review_result_from_output(output, expected_pass):
    result = ReviewResult.from_output(output)
    assert result.passed == expected_pass


def test_review_result_feedback_on_fail():
    result = ReviewResult.from_output("REJECTED: bad code")
    assert "bad code" in result.feedback


def test_review_result_no_feedback_on_pass():
    result = ReviewResult.from_output("APPROVED")
    assert result.feedback == ""


# ---------------------------------------------------------------------------
# TicketState defaults
# ---------------------------------------------------------------------------

def test_ticket_state_defaults():
    s = TicketState(jira_key="PROJ-1")
    assert s.status == "running"
    assert s.code_review_retries == 0
    assert s.max_retries == 3
    assert s.task_outputs == {}


# ---------------------------------------------------------------------------
# TicketFlow: happy path (all gates pass first try)
# ---------------------------------------------------------------------------

def _make_flow(max_retries=3):
    state = TicketState(jira_key="PROJ-99", max_retries=max_retries)
    updates = []
    flow = TicketFlow(state, on_status=lambda s: updates.append(s.current_task))
    return flow, updates


def test_flow_happy_path():
    flow, _ = _make_flow()
    with patch("code_crew.flow.TicketFlow._execute", return_value="APPROVED"):
        result = flow.run()
    assert result.status == "passed"
    assert result.code_review_retries == 0


def test_flow_emits_task_names():
    flow, updates = _make_flow()
    with patch("code_crew.flow.TicketFlow._execute", return_value="APPROVED"):
        flow.run()
    assert "sprint_planning" in updates
    assert "code_review" in updates
    assert "dod_check" in updates


# ---------------------------------------------------------------------------
# TicketFlow: retry on code review failure
# ---------------------------------------------------------------------------

def test_flow_retries_on_code_review_fail():
    flow, _ = _make_flow(max_retries=2)
    review_calls = {"n": 0}

    def mock_execute(task_name):
        if task_name == "code_review":
            review_calls["n"] += 1
            if review_calls["n"] < 2:  # fail first time, pass second
                return "REJECTED: bad code"
        return "APPROVED"

    with patch("code_crew.flow.TicketFlow._execute", side_effect=mock_execute):
        result = flow.run()

    assert result.status == "passed"
    assert result.code_review_retries == 1  # incremented once before passing


def test_flow_escalates_after_max_retries():
    flow, _ = _make_flow(max_retries=1)
    feedback_injected = threading.Event()

    def mock_execute(task_name):
        if task_name == "code_review":
            return "REJECTED: persistent issue"
        return "APPROVED"

    def inject_after_escalation():
        # Wait until needs_help, then inject guidance
        while flow.state.status != "needs_help":
            threading.Event().wait(0.01)
        flow.inject_feedback("Fix the layer violation by using the repository interface.")
        feedback_injected.set()

    injector = threading.Thread(target=inject_after_escalation, daemon=True)
    injector.start()

    call_tracker = {"code_review_calls": 0}
    orig_execute = mock_execute

    def tracked_execute(task_name):
        if task_name == "code_review":
            call_tracker["code_review_calls"] += 1
            if call_tracker["code_review_calls"] <= 2:
                return "REJECTED: persistent issue"
        return "APPROVED"

    with patch("code_crew.flow.TicketFlow._execute", side_effect=tracked_execute):
        result = flow.run()

    assert feedback_injected.is_set()
    assert result.status == "passed"


def test_flow_review_feedback_injected_in_next_execute():
    """Feedback from code_review is included in the next backend_implementation call."""
    flow, _ = _make_flow(max_retries=1)
    received_contexts = []

    def mock_execute(task_name):
        # Capture what was in human_feedback when impl runs
        if task_name == "backend_implementation":
            received_contexts.append(flow.state.review_feedback)
        if task_name == "code_review" and len(received_contexts) == 1:
            return "REJECTED: fix the handler"
        return "APPROVED"

    # Prevent infinite loop by injecting help after first escalation
    def inject():
        while flow.state.status != "needs_help":
            threading.Event().wait(0.01)
        flow.inject_feedback("guidance")

    t = threading.Thread(target=inject, daemon=True)
    t.start()

    with patch("code_crew.flow.TicketFlow._execute", side_effect=mock_execute):
        flow.run()

    # Second impl call should have the review feedback set
    assert any("fix the handler" in (ctx or "") for ctx in received_contexts[1:])


# ---------------------------------------------------------------------------
# inject_feedback
# ---------------------------------------------------------------------------

def test_inject_feedback_resumes_flow():
    flow, _ = _make_flow(max_retries=0)
    resumed = threading.Event()
    impl_calls = {"n": 0}

    def mock_execute(task_name):
        if task_name == "backend_implementation":
            impl_calls["n"] += 1
            if impl_calls["n"] >= 2 and flow.state.human_feedback:
                resumed.set()
        if task_name == "code_review":
            # Pass once human feedback has been delivered (second impl run onwards)
            if impl_calls["n"] >= 2:
                return "APPROVED"
            return "REJECTED"
        return "APPROVED"

    def inject():
        while flow.state.status != "needs_help":
            threading.Event().wait(0.01)
        flow.inject_feedback("try again")

    t = threading.Thread(target=inject, daemon=True)
    t.start()

    with patch("code_crew.flow.TicketFlow._execute", side_effect=mock_execute):
        flow.run()

    assert resumed.is_set()
