import pytest


@pytest.fixture(autouse=True)
def make_code_crew_dir(tmp_path, request):
    """Pre-create .code-crew/ in tmp_path for tests that write config.yaml there."""
    if "tmp_path" in request.fixturenames:
        (tmp_path / ".code-crew").mkdir(exist_ok=True)
