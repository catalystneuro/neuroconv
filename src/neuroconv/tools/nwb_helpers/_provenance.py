"""Build the provenance record that NeuroConv writes into ``general/source_script``."""

import functools
import importlib.metadata
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PROVENANCE_FORMAT_VERSION = 1
RECORD_HEADER = "NeuroConv provenance record"

_PROVENANCE_ENVIRONMENT_VARIABLE = "NEUROCONV_PROVENANCE"
_FULL_GIT_INFO = "full-git-info"

# `sys.argv[0]` values that mean no script was run at all.
_NOT_A_SCRIPT_ARGUMENTS = {"", "-c", "-"}
_LAUNCHER_FILE_NAMES = {"ipykernel_launcher.py"}
_INSTALLED_LIBRARY_DIRECTORIES = {"site-packages", "dist-packages"}

_NO_SCRIPT_FILE_NAME = "neuroconv"

# A URL is only built for hosts whose layout we know. The remote names the host but not the software
# running on it, so a self-hosted forge could be any of these and is left out.
_URL_LAYOUT_BY_HOST = {
    "github.com": "{repository}/blob/{commit}/{path}",
    "gitlab.com": "{repository}/-/blob/{commit}/{path}",
    "bitbucket.org": "{repository}/src/{commit}/{path}",
}

_GIT_TIMEOUT_IN_SECONDS = 10.0

_SCP_LIKE_REMOTE = re.compile(r"^[^/@]+@([^:/]+):(.+)$")


def describe_source_script() -> tuple[str, str]:
    """
    Return ``(source_script, source_script_file_name)`` for the running conversion.

    Returns
    -------
    tuple of str
        The provenance record and the name of the script that is running it. See
        ``docs/developer_guide/provenance.rst`` for the format of the record.
    """
    neuroconv_version = importlib.metadata.version("neuroconv")
    script = _resolve_script()

    keys = {
        "neuroconv_version": neuroconv_version,
        "execution_environment": _describe_execution_environment(),
    }
    if script is None:
        return _render(keys), _NO_SCRIPT_FILE_NAME

    keys["source_script"] = script.name
    if _git_information_is_requested():
        directory = str(_script_directory(script=script))
        git_keys, repository_root = _describe_git_checkout(directory=directory)
        path_in_repository = _path_in_repository(script=script, repository_root=repository_root)
        if path_in_repository is not None:
            keys["source_script"] = path_in_repository
        # Resolved, because `sys.argv[0]` may be relative to the working directory rather than to `directory`
        if _script_is_tracked(directory=directory, script=str(script.resolve())):
            script_url = _build_script_url_at_commit(path_in_repository=path_in_repository, git_keys=git_keys)
            if script_url is not None:
                keys["source_script"] = script_url
        keys.update(git_keys)

    return _render(keys), script.name


def _render(keys: dict[str, str]) -> str:
    """Render the record: a header naming it, the keys, then the format it is written in."""
    lines = [RECORD_HEADER]
    lines.extend(f"{key}: {value}" for key, value in keys.items())
    lines.append(f"neuroconv_provenance_format: {PROVENANCE_FORMAT_VERSION}")

    return "\n".join(lines)


def _git_information_is_requested() -> bool:
    """Whether the git keys should be written, according to ``NEUROCONV_PROVENANCE``."""
    # Anything other than the explicit opt in disables the git keys, so a typo discloses less rather
    # than more.
    value = os.environ.get(_PROVENANCE_ENVIRONMENT_VARIABLE, _FULL_GIT_INFO)
    return value.strip().lower() == _FULL_GIT_INFO


def _resolve_script() -> Path | None:
    """
    Return the user's conversion script, or None when what is running is not one.

    A test runner, a console entry point and a module inside an installed library all run as scripts
    but are not the conversion, and pointing at them would describe the environment rather than the
    work. Notably, a plain pytest run resolves into whatever repository the environment lives in.
    """
    argument = sys.argv[0] if sys.argv else ""
    if argument in _NOT_A_SCRIPT_ARGUMENTS:
        return None

    script = Path(argument)
    if script.name in _LAUNCHER_FILE_NAMES:
        return None
    if script.suffix != ".py":  # a console entry point, such as `pytest` or our own `neuroconv`
        return None
    if _INSTALLED_LIBRARY_DIRECTORIES.intersection(script.resolve().parts):  # `python -m some_library`
        return None

    return script


def _describe_execution_environment() -> str:
    """One of ``script``, ``notebook`` or ``interactive``."""
    argument = sys.argv[0] if sys.argv else ""
    if Path(argument).name in _LAUNCHER_FILE_NAMES:
        return "notebook"

    shell_name = _ipython_shell_name()
    if shell_name == "ZMQInteractiveShell":
        return "notebook"
    if shell_name is not None or argument in _NOT_A_SCRIPT_ARGUMENTS:
        return "interactive"

    return "script"


def _ipython_shell_name() -> str | None:
    try:
        from IPython import get_ipython
    except ImportError:
        return None

    shell = get_ipython()
    return None if shell is None else type(shell).__name__


def _script_directory(script: Path) -> Path:
    """The directory to run git from, which is the script's own rather than the working directory."""
    return script.resolve().parent


@functools.cache
def _describe_git_checkout(directory: str) -> tuple[dict[str, str], str | None]:
    """
    Describe the git checkout containing `directory`, if there is one.

    Cached because the metadata helpers run once per interface, and this is the only part of the
    record that costs subprocesses. The environment variable is deliberately read outside of it.

    Returns
    -------
    tuple
        The record keys, in the order they are written, and the repository root.
    """
    commit = _run_git(directory, "rev-parse", "HEAD")
    if commit is None:
        return {"version_control": "none"}, None

    keys = {"version_control": "git"}

    remote = _run_git(directory, "config", "--get", "remote.origin.url")
    repository = _normalize_remote(remote=remote) if remote else None
    if repository is not None:
        keys["repository"] = repository

    keys["commit"] = commit

    commit_date = _run_git(directory, "show", "--no-patch", "--format=%cI", commit)
    if commit_date:
        keys["commit_date"] = commit_date

    status = _run_git(directory, "status", "--porcelain", "--untracked-files=no")
    if status is not None:
        keys["working_tree"] = "modified" if status else "clean"

    containing_branches = _run_git(directory, "branch", "--remotes", "--contains", commit)
    if containing_branches is not None:
        keys["commit_published"] = "yes" if containing_branches else "no"

    return keys, _run_git(directory, "rev-parse", "--show-toplevel")


def _run_git(directory: str, *arguments: str) -> str | None:
    """Run a git command, returning None rather than raising when it cannot be run."""
    try:
        completed_process = subprocess.run(
            ["git", "-C", directory, *arguments],
            capture_output=True,
            # Git writes UTF-8, and the locale default is cp1252 on Windows, where a path or a commit
            # message outside ASCII would decode into something else.
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_IN_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):  # no git binary, unreadable directory, timeout
        return None

    if completed_process.returncode != 0:
        return None

    return completed_process.stdout.strip()


def _normalize_remote(remote: str) -> str | None:
    """Normalize a git remote to an HTTPS URL, dropping any credentials it carries."""
    remote = remote.strip()

    scp_like_match = _SCP_LIKE_REMOTE.match(remote)
    if scp_like_match is not None:
        host, path = scp_like_match.groups()
    else:
        parsed_remote = urlparse(remote)
        if parsed_remote.hostname is None:  # a local path, for example
            return None
        host, path = parsed_remote.hostname, parsed_remote.path

    path = path.strip("/").removesuffix(".git")
    if not path:
        return None

    return f"https://{host}/{path}"


def _path_in_repository(script: Path, repository_root: str | None) -> str | None:
    """The script's path relative to the repository root, which describes the repository, not the disk."""
    if repository_root is None:
        return None

    try:
        return script.resolve().relative_to(Path(repository_root).resolve()).as_posix()
    except ValueError:
        return None


@functools.cache
def _script_is_tracked(directory: str, script: str) -> bool:
    """
    Whether git knows the script at all.

    An untracked script is absent from the commit even when the working tree is otherwise clean, since
    ``--untracked-files=no`` does not count it, so a URL built for it would resolve to nothing.

    Cached for the same reason the checkout description is: the metadata helpers run once per interface.
    """
    return _run_git(directory, "ls-files", "--error-unmatch", script) is not None


def _build_script_url_at_commit(path_in_repository: str | None, git_keys: dict[str, str]) -> str | None:
    """
    Build a URL to the script as it stood at the recorded commit.

    Returns None when such a URL cannot be trusted or built.

    A link to a commit that is not what ran looks authoritative and is wrong, which is worse than no
    link, so this requires a clean working tree and a commit that has been pushed.
    """
    repository = git_keys.get("repository")
    if path_in_repository is None or repository is None:
        return None
    if git_keys.get("working_tree") != "clean" or git_keys.get("commit_published") != "yes":
        return None
    layout = _URL_LAYOUT_BY_HOST.get(urlparse(repository).hostname)
    if layout is None:
        return None

    return layout.format(repository=repository, commit=git_keys["commit"], path=path_in_repository)
