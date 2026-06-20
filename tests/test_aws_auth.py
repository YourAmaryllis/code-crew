"""Tests for shared.aws_auth."""

import subprocess
from unittest.mock import patch, MagicMock

from shared.aws_auth import is_aws_auth_error, sso_login


# ---------------------------------------------------------------------------
# is_aws_auth_error — type-name matching
# ---------------------------------------------------------------------------

def _exc(name: str, msg: str = "some error") -> Exception:
    """Create an exception whose class __name__ matches `name`."""
    cls = type(name, (Exception,), {})
    return cls(msg)


def test_detects_unauthorized_sso_token():
    assert is_aws_auth_error(_exc("UnauthorizedSSOTokenError", "Token has expired"))


def test_detects_sso_token_load_error():
    assert is_aws_auth_error(_exc("SSOTokenLoadError"))


def test_detects_no_credentials_error():
    assert is_aws_auth_error(_exc("NoCredentialsError", "Unable to locate credentials"))


def test_detects_token_retrieval_error():
    assert is_aws_auth_error(_exc("TokenRetrievalError"))


# ---------------------------------------------------------------------------
# is_aws_auth_error — ClientError response dict
# ---------------------------------------------------------------------------

def test_detects_expired_token_via_response():
    exc = Exception("An error occurred")
    exc.response = {"Error": {"Code": "ExpiredTokenException", "Message": "..."}}
    assert is_aws_auth_error(exc)


def test_detects_access_denied_via_response():
    exc = Exception("An error occurred")
    exc.response = {"Error": {"Code": "AccessDeniedException", "Message": "..."}}
    assert is_aws_auth_error(exc)


def test_ignores_non_auth_client_error():
    exc = Exception("Resource not found")
    exc.response = {"Error": {"Code": "ResourceNotFoundException", "Message": "..."}}
    assert not is_aws_auth_error(exc)


# ---------------------------------------------------------------------------
# is_aws_auth_error — string heuristics
# ---------------------------------------------------------------------------

def test_detects_via_string_token_has_expired():
    assert is_aws_auth_error(Exception("Token has expired and refresh failed"))


def test_detects_via_string_unable_to_locate_credentials():
    assert is_aws_auth_error(Exception("Unable to locate credentials"))


def test_detects_via_string_sso_token():
    assert is_aws_auth_error(Exception("The SSO token is no longer valid"))


def test_does_not_false_positive_on_random_error():
    assert not is_aws_auth_error(Exception("Connection timeout"))
    assert not is_aws_auth_error(ValueError("invalid input"))
    assert not is_aws_auth_error(KeyError("BEDROCK_MODEL_ID"))


# ---------------------------------------------------------------------------
# is_aws_auth_error — cause chain
# ---------------------------------------------------------------------------

def test_detects_via_cause_chain():
    root = _exc("UnauthorizedSSOTokenError", "expired")
    wrapper = Exception("LLM call failed")
    wrapper.__cause__ = root
    assert is_aws_auth_error(wrapper)


# ---------------------------------------------------------------------------
# sso_login
# ---------------------------------------------------------------------------

def test_sso_login_no_profile_calls_aws_sso_login():
    with patch("shared.aws_auth.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = sso_login()
    mock_run.assert_called_once_with(["aws", "sso", "login"])
    assert result is True


def test_sso_login_with_profile_adds_flag():
    with patch("shared.aws_auth.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        sso_login(profile="my-aws-profile")
    mock_run.assert_called_once_with(["aws", "sso", "login", "--profile", "my-aws-profile"])


def test_sso_login_returns_false_on_nonzero_exit():
    with patch("shared.aws_auth.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = sso_login()
    assert result is False
