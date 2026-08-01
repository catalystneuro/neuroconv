"""The Python version CI tests against must agree with the one the package claims to support."""

from pathlib import Path

import tomllib

REPOSITORY_ROOT = Path(__file__).parent.parent.parent
WORKFLOWS_PATH = REPOSITORY_ROOT / ".github" / "workflows"


def test_minimum_python_version_matches_requires_python():
    """`min_python_version.txt` drives the CI matrix, `requires-python` drives what pip will install.

    They are edited in different files by different pull requests, so nothing but this stops CI from
    quietly dropping the oldest version neuroconv still claims to support.
    """
    minimum_version = (WORKFLOWS_PATH / "min_python_version.txt").read_text(encoding="utf-8").strip()

    pyproject = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires_python = pyproject["project"]["requires-python"]

    assert requires_python == f">={minimum_version}"
