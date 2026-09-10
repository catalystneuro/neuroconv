#!/usr/bin/env python3
"""
Report whether a pull request changed the installation extras rather than some other part of `pyproject.toml`.

The formatwise gallery job exists to catch an extra moving out from under a gallery page, so it needs to run
when the extras table changes. It does not need to run because the version string moved, a tool's
configuration was edited, or a dependency floor was bumped, all of which live in the same file.

Prints "true" or "false". Fails open, printing "true", when the base revision cannot be read, since running
the sweep needlessly costs only time while skipping it wrongly is the failure the job exists to prevent.
"""

import re
import subprocess
import sys
from pathlib import Path

SECTION = "[project.optional-dependencies]"


def optional_dependencies(text: str) -> str | None:
    """Return the body of the optional-dependencies table, or None if the file does not declare one."""
    match = re.search(rf"^{re.escape(SECTION)}\n(.*?)(?=^\[)", text, re.S | re.M)
    return match.group(1) if match else None


def main() -> None:
    """Compare the extras table at the base revision with the one in the working tree."""
    if len(sys.argv) != 2:
        print("usage: optional_dependencies_changed.py <base-ref>", file=sys.stderr)
        sys.exit(2)

    base_ref = sys.argv[1]
    if not base_ref:
        print("No base revision given, assuming the extras changed", file=sys.stderr)
        print("true")
        return

    completed = subprocess.run(
        ["git", "show", f"{base_ref}:pyproject.toml"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(f"Could not read pyproject.toml at {base_ref}, assuming the extras changed", file=sys.stderr)
        print("true")
        return

    head = optional_dependencies(Path("pyproject.toml").read_text(encoding="utf-8"))
    base = optional_dependencies(completed.stdout)
    print("true" if head != base else "false")


if __name__ == "__main__":
    main()
