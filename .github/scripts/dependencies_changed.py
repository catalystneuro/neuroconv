#!/usr/bin/env python3
"""
Report whether a pull request changed what `pip install .[extra]` resolves to, rather than some other part
of `pyproject.toml`.

The formatwise gallery job exists to catch a gallery page's installation breaking, so it needs to run when
`project.dependencies` or `project.optional-dependencies` changes. Base dependencies count because every
isolated `.[extra]` environment installs them too. It does not need to run because the version string moved
or a tool's configuration was edited, which live in the same file.

The two tables are compared as parsed TOML rather than as text, so reordering, comments and whitespace do
not trigger a sweep, and a table sitting last in the file is read like any other.

Prints "true" or "false". Fails open, printing "true", when either revision cannot be read or parsed, since
running the sweep needlessly costs only time while skipping it wrongly is the failure the job exists to
prevent.
"""

import subprocess
import sys
from pathlib import Path

import tomllib


def installation_tables(text: str) -> tuple:
    """Return the two tables that decide what an `.[extra]` install resolves to."""
    project = tomllib.loads(text).get("project", {})
    return project.get("dependencies"), project.get("optional-dependencies")


def main() -> None:
    """Compare the installation tables at the base revision with the ones in the working tree."""
    if len(sys.argv) != 2:
        print("usage: dependencies_changed.py <base-ref>", file=sys.stderr)
        sys.exit(2)

    base_ref = sys.argv[1]
    if not base_ref:
        print("No base revision given, assuming the dependencies changed", file=sys.stderr)
        print("true")
        return

    completed = subprocess.run(
        ["git", "show", f"{base_ref}:pyproject.toml"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(f"Could not read pyproject.toml at {base_ref}, assuming the dependencies changed", file=sys.stderr)
        print("true")
        return

    try:
        base = installation_tables(completed.stdout)
        head = installation_tables(Path("pyproject.toml").read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        print(f"Could not parse pyproject.toml ({error}), assuming the dependencies changed", file=sys.stderr)
        print("true")
        return

    print("true" if head != base else "false")


if __name__ == "__main__":
    main()
