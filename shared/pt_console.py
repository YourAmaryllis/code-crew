"""
prompt_toolkit-safe Rich Console.

patch_stdout() replaces sys.stdout with a proxy that corrupts the ESC byte
(\x1b → ?), breaking all Rich ANSI colour codes.

Fix: pass a _PTFile as the Console's underlying file.  _PTFile.write() routes
every byte through print_formatted_text(ANSI(...)), which uses prompt_toolkit's
own terminal output path and preserves ANSI codes.

This covers *all* Console output paths (print, log, _check_buffer, Live) —
not just print() — so third-party code like CrewAI's ConsoleFormatter also
renders correctly when its .console attribute is replaced with PTConsole.
"""

from __future__ import annotations

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import ANSI
from rich.console import Console


class _PTFile:
    """File-like object that routes writes through prompt_toolkit output."""

    encoding = "utf-8"
    errors = "replace"

    def write(self, text: str) -> int:
        if text:
            print_formatted_text(ANSI(text), end="")
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True


def pt_print(fragments: list[tuple[str, str]]) -> None:
    """Print styled text above the prompt_toolkit prompt from any thread.

    fragments: list of (style, text) tuples — same format as FormattedText.
    Works correctly inside patch_stdout() context.
    """
    from prompt_toolkit.formatted_text import FormattedText
    print_formatted_text(FormattedText(fragments))


class PTConsole(Console):
    """Drop-in for rich.Console that works inside prompt_toolkit's patch_stdout.

    All output goes through _PTFile → print_formatted_text(ANSI(...)), bypassing
    the patched sys.stdout proxy entirely.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("force_terminal", True)
        kwargs.setdefault("highlight", False)
        super().__init__(file=_PTFile(), **kwargs)
