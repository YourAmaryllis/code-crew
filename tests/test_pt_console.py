"""Tests for shared.pt_console."""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# _PTFile
# ---------------------------------------------------------------------------

def test_ptfile_write_calls_print_formatted_text():
    """_PTFile.write() must route text through print_formatted_text(ANSI(...))."""
    from prompt_toolkit.formatted_text import ANSI
    from shared.pt_console import _PTFile

    received = []

    def fake_ptpf(ft, end=""):
        received.append(ft)

    with patch("shared.pt_console.print_formatted_text", side_effect=fake_ptpf):
        f = _PTFile()
        f.write("\x1b[33mhello\x1b[0m\n")

    assert len(received) == 1
    assert isinstance(received[0], ANSI)
    assert "hello" in received[0].value


def test_ptfile_write_skips_empty():
    """_PTFile.write('') must not call print_formatted_text."""
    with patch("shared.pt_console.print_formatted_text") as mock_ptpf:
        from shared.pt_console import _PTFile
        _PTFile().write("")
    mock_ptpf.assert_not_called()


def test_ptfile_write_returns_length():
    with patch("shared.pt_console.print_formatted_text"):
        from shared.pt_console import _PTFile
        n = _PTFile().write("hello")
    assert n == 5


def test_ptfile_isatty():
    from shared.pt_console import _PTFile
    assert _PTFile().isatty() is True


# ---------------------------------------------------------------------------
# PTConsole
# ---------------------------------------------------------------------------

def test_ptconsole_routes_through_print_formatted_text():
    """console.print() must ultimately call print_formatted_text, not sys.stdout."""
    from prompt_toolkit.formatted_text import ANSI
    from shared.pt_console import PTConsole

    received = []

    def fake_ptpf(ft, end=""):
        received.append(ft)

    with patch("shared.pt_console.print_formatted_text", side_effect=fake_ptpf):
        c = PTConsole()
        c.print("[bold]hello[/bold]")

    assert any("hello" in str(ft.value) for ft in received), \
        f"Expected 'hello' in output, got: {[ft.value for ft in received]}"


def test_ptconsole_does_not_write_to_sys_stdout():
    """Nothing must be written to sys.stdout (which is patched by patch_stdout)."""
    import sys
    from shared.pt_console import PTConsole

    class _FakeStdout:
        written: list[str] = []
        def write(self, s): self.written.append(s)
        def flush(self): pass

    fake = _FakeStdout()
    real_stdout = sys.stdout
    sys.stdout = fake
    try:
        with patch("shared.pt_console.print_formatted_text"):
            c = PTConsole()
            c.print("test output")
    finally:
        sys.stdout = real_stdout

    assert not fake.written, f"Unexpected writes to sys.stdout: {fake.written}"


def test_ptconsole_ansi_wrapper_used():
    """print_formatted_text must receive ANSI() objects, not plain strings."""
    from prompt_toolkit.formatted_text import ANSI
    from shared.pt_console import PTConsole

    received = []

    with patch("shared.pt_console.print_formatted_text", side_effect=lambda ft, end="": received.append(ft)):
        c = PTConsole()
        c.print("anything")

    assert received, "print_formatted_text was never called"
    assert all(isinstance(ft, ANSI) for ft in received), \
        f"Expected all ANSI objects, got: {[type(ft) for ft in received]}"
