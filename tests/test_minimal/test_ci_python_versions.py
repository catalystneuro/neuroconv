"""The Python version CI tests against must agree with the one the package claims to support."""

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parent.parent.parent
WORKFLOWS_PATH = REPOSITORY_ROOT / ".github" / "workflows"


def test_minimum_python_version_matches_requires_python():
    """`min_python_version.txt` drives the CI matrix, `requires-python` drives what pip will install.

    They are edited in different files by different pull requests, so nothing but this stops CI from
    quietly dropping the oldest version neuroconv still claims to support.

    `pyproject.toml` is read as text rather than parsed, since `tomllib` is only stdlib from 3.11 and this
    has to run on the minimum version it is asserting.
    """
    minimum_version = (WORKFLOWS_PATH / "min_python_version.txt").read_text(encoding="utf-8").strip()

    pyproject_text = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requires_python = re.search(r'^requires-python\s*=\s*"([^"]+)"', pyproject_text, flags=re.MULTILINE).group(1)

    assert requires_python == f">={minimum_version}"
