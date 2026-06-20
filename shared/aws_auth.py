"""
AWS credential / SSO-expiry detection and recovery.

Usage:
    from shared.aws_auth import is_aws_auth_error, sso_login

    try:
        result = some_bedrock_call()
    except Exception as exc:
        if is_aws_auth_error(exc):
            ok = sso_login(profile=os.environ.get("AWS_PROFILE"))
            ...
"""

from __future__ import annotations

import os
import subprocess

# botocore exception class names that indicate auth failure
_AUTH_TYPE_NAMES = frozenset({
    "UnauthorizedSSOTokenError",
    "SSOTokenLoadError",
    "TokenRetrievalError",
    "NoCredentialsError",
    "PartialCredentialsError",
    "ExpiredTokenException",
    "InvalidIdentityTokenException",
})

# ClientError codes that mean auth/token failure
_AUTH_ERROR_CODES = frozenset({
    "ExpiredTokenException",
    "ExpiredToken",
    "AccessDeniedException",
    "UnrecognizedClientException",
    "AuthFailure",
    "InvalidClientTokenId",
    "RequestExpired",
})

# Substrings to match against str(exc) when the type name isn't conclusive
_AUTH_PHRASES = (
    "token has expired",
    "sso token",
    "no credentials",
    "unable to locate credentials",
    "expired token",
    "access denied",
    "not authorized",
    "invalidclienttokenid",
    "aws sso",
)


def is_aws_auth_error(exc: BaseException) -> bool:
    """Return True if exc looks like an expired/missing AWS credential error."""
    # Check the exception class name (works even without importing botocore)
    type_name = type(exc).__name__
    if type_name in _AUTH_TYPE_NAMES:
        return True

    # ClientError has a .response dict with an Error.Code
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code", "")
        if code in _AUTH_ERROR_CODES:
            return True

    # Walk the cause chain — botocore often wraps the root error
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause is not None and cause is not exc:
        if is_aws_auth_error(cause):
            return True

    # String heuristic as last resort
    msg = str(exc).lower()
    return any(phrase in msg for phrase in _AUTH_PHRASES)


def sso_login(profile: str | None = None) -> bool:
    """
    Run `aws sso login [--profile PROFILE]` interactively (inherits terminal).
    Returns True if the command exited 0.
    """
    cmd = ["aws", "sso", "login"]
    if profile:
        cmd += ["--profile", profile]
    result = subprocess.run(cmd)   # stdin/stdout/stderr inherited → browser flow works
    return result.returncode == 0
