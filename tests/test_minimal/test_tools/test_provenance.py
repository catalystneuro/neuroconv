"""Tests for the provenance record written into ``general/source_script``."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from pynwb import read_nwb

from neuroconv.tools.nwb_helpers import _provenance
from neuroconv.tools.nwb_helpers._provenance import describe_source_script


@pytest.fixture(autouse=True)
def clear_git_cache():
    """The git description is cached per directory, which must not carry across tests."""
    _provenance._describe_git_checkout.cache_clear()
    _provenance._script_is_tracked.cache_clear()
    yield
    _provenance._describe_git_checkout.cache_clear()
    _provenance._script_is_tracked.cache_clear()


def parse_record(record: str) -> dict:
    """Parse the record the way a survey would: keep the `key: value` lines, ignore the first line."""
    matches = (re.match(r"^([a-z_]+): (.*)$", line) for line in record.splitlines())
    return {match.group(1): match.group(2) for match in matches if match is not None}


def run_git(directory, *arguments) -> str:
    completed_process = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, encoding="utf-8")
    assert completed_process.returncode == 0, completed_process.stderr
    return completed_process.stdout.strip()


def make_repository(directory, remote: str = "https://github.com/lab/conversions.git") -> str:
    """
    Build a repository holding a conversion script and return the script's path.

    The script imports a module beside it, which is the ordinary shape of a lab conversion repository
    and the reason the working tree is read across the whole repository rather than the script alone.
    """
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "convert_lab.py"
    script.write_text("import lab_utils\n\nprint('converting')\n", encoding="utf-8")
    (directory / "lab_utils.py").write_text("SAMPLING_FREQUENCY = 30_000.0\n", encoding="utf-8")

    run_git(directory, "init", "--quiet")
    run_git(directory, "config", "user.email", "lab@example.com")
    run_git(directory, "config", "user.name", "Lab")
    run_git(directory, "config", "commit.gpgsign", "false")
    run_git(directory, "add", "convert_lab.py", "lab_utils.py")
    run_git(directory, "commit", "--quiet", "--message", "add the conversion")
    run_git(directory, "remote", "add", "origin", remote)

    return str(script)


def publish(directory) -> None:
    """Make the commit reachable from a remote branch without touching the network."""
    run_git(directory, "update-ref", "refs/remotes/origin/main", run_git(directory, "rev-parse", "HEAD"))


CONVERSION_SCRIPT = """
from datetime import datetime

from neuroconv.tools.nwb_helpers import (
    configure_and_write_nwbfile,
    get_default_nwbfile_metadata,
    make_nwbfile_from_metadata,
)

import lab_utils

metadata = get_default_nwbfile_metadata()
metadata["NWBFile"]["session_start_time"] = datetime(2026, 1, 1)
nwbfile = make_nwbfile_from_metadata(metadata=metadata)
configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=r"{nwbfile_path}")
"""


def test_the_record_reaches_the_written_file(tmp_path):
    """
    End to end, in a subprocess, so `sys.argv[0]` is a real script rather than a monkeypatched one.

    This is the only test that sees what a conversion actually produces: the record surviving an HDF5
    round trip, and the attribute holding a name rather than the path of a module on this machine.
    """
    repository = tmp_path / "conversions"
    script = Path(make_repository(repository))
    nwbfile_path = tmp_path / "converted.nwb"
    script.write_text(CONVERSION_SCRIPT.format(nwbfile_path=nwbfile_path), encoding="utf-8")
    run_git(repository, "commit", "--quiet", "--all", "--message", "write a file")
    publish(repository)

    subprocess.run([sys.executable, str(script)], cwd=tmp_path, check=True, capture_output=True, encoding="utf-8")

    nwbfile = read_nwb(nwbfile_path)
    keys = parse_record(nwbfile.source_script)

    commit = run_git(repository, "rev-parse", "HEAD")
    assert nwbfile.source_script.splitlines()[0] == "NeuroConv provenance record"
    assert keys["neuroconv_provenance_format"] == "1"
    assert keys["execution_environment"] == "script"
    assert keys["repository"] == "https://github.com/lab/conversions"
    assert keys["commit"] == commit
    assert keys["source_script"] == f"https://github.com/lab/conversions/blob/{commit}/convert_lab.py"
    assert nwbfile.source_script_file_name == "convert_lab.py"
    assert str(tmp_path) not in nwbfile.source_script


def neuroconv_checkout() -> Path | None:
    """The repository NeuroConv is being tested from, or None when it is not a git checkout."""
    completed_process = subprocess.run(
        ["git", "-C", str(Path(__file__).parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        encoding="utf-8",
    )
    return Path(completed_process.stdout.strip()) if completed_process.returncode == 0 else None


def test_the_record_describes_a_real_checkout(tmp_path):
    """
    Run a script from inside NeuroConv's own repository rather than a synthetic one.

    The repositories built above are ideal: one commit, a remote we chose, a ref layout we wrote. A real
    checkout is where the awkward cases live, a shallow clone, a detached HEAD, a fork under a different
    owner, or a remote carrying a credential, and this is the only test that meets one. What is asserted
    is computed from git here rather than hardcoded, so it holds on a fork as well as on the main
    repository.
    """
    checkout = neuroconv_checkout()
    if checkout is None:
        pytest.skip("NeuroConv is not being tested from a git checkout")

    remote = subprocess.run(
        ["git", "-C", str(checkout), "config", "--get", "remote.origin.url"], capture_output=True, encoding="utf-8"
    )
    if remote.returncode != 0:
        pytest.skip("the checkout has no origin remote")

    script = checkout / "provenance_from_a_real_checkout.py"
    script.write_text(
        "from neuroconv.tools.nwb_helpers._provenance import describe_source_script\nprint(describe_source_script()[0])\n",
        encoding="utf-8",
    )
    try:
        completed_process = subprocess.run(
            [sys.executable, str(script)], cwd=tmp_path, check=True, capture_output=True, encoding="utf-8"
        )
    finally:
        script.unlink()

    record = completed_process.stdout
    keys = parse_record(record)
    expected_name = remote.stdout.strip().rstrip("/").removesuffix(".git").rsplit("/", 1)[-1].rsplit(":", 1)[-1]

    assert keys["version_control"] == "git"
    assert keys["commit"] == run_git(checkout, "rev-parse", "HEAD")
    assert keys["repository"].startswith("https://")
    assert keys["repository"].endswith(f"/{expected_name}")
    assert "@" not in keys["repository"]  # a credential in the remote is never written
    assert keys["commit_published"] in {"yes", "no"}
    # The script was written for this test and never committed, so it is absent from the commit
    assert keys["source_script"] == "provenance_from_a_real_checkout.py"
    assert str(Path.home()) not in record


def test_a_plain_pytest_run_names_no_repository():
    """
    The suite runs inside NeuroConv's own repository.

    Anything resolving ``sys.argv[0]`` without care would describe this checkout and write a
    catalystneuro/neuroconv URL into the files the tests produce.
    """
    source_script, source_script_file_name = describe_source_script()

    assert "repository" not in parse_record(source_script)
    assert source_script_file_name == "neuroconv"


def test_the_record_names_itself_on_its_first_line():
    source_script, _ = describe_source_script()

    assert source_script.splitlines()[0] == "NeuroConv provenance record"


def test_the_format_is_stated_on_the_last_line():
    source_script, _ = describe_source_script()

    assert source_script.splitlines()[-1] == "neuroconv_provenance_format: 1"


def test_the_record_always_states_its_format_and_version():
    keys = parse_record(describe_source_script()[0])

    assert keys["neuroconv_provenance_format"] == "1"
    assert keys["neuroconv_version"]


def test_clean_and_published_script(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    commit = run_git(tmp_path / "conversions", "rev-parse", "HEAD")
    assert keys["execution_environment"] == "script"
    assert keys["version_control"] == "git"
    assert keys["repository"] == "https://github.com/lab/conversions"
    assert keys["commit"] == commit
    assert keys["commit_date"]
    assert keys["working_tree"] == "clean"
    assert keys["commit_published"] == "yes"
    assert keys["source_script"] == f"https://github.com/lab/conversions/blob/{commit}/convert_lab.py"
    assert source_script_file_name == "convert_lab.py"


def test_modified_working_tree_writes_no_script_url(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    (tmp_path / "conversions" / "convert_lab.py").write_text("print('converting differently')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["working_tree"] == "modified"
    assert keys["source_script"] == "convert_lab.py"
    assert keys["commit"]  # the sha is still stated, it is only the link that is withheld


def test_a_modified_module_beside_the_script_modifies_the_working_tree(tmp_path, monkeypatch):
    """
    The script is not the only code that ran.

    A conversion script imports modules from its own repository, so an edit to one of them means the
    commit no longer describes what ran even though the script itself is untouched. Reading the working
    tree across the whole repository rather than the script alone is what catches this.
    """
    script = make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    (tmp_path / "conversions" / "lab_utils.py").write_text("SAMPLING_FREQUENCY = 25_000.0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["working_tree"] == "modified"
    assert keys["source_script"] == "convert_lab.py"


def test_an_untracked_script_writes_no_script_url(tmp_path, monkeypatch):
    """
    A script git does not know is absent from the commit, so a URL for it would resolve to nothing.

    `--untracked-files=no` means the working tree still reads clean, which is correct for the tree and
    exactly why the script's own tracking has to be checked separately.
    """
    make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    script = tmp_path / "conversions" / "convert_lab_draft.py"
    script.write_text("import lab_utils\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script)])

    keys = parse_record(describe_source_script()[0])

    assert keys["working_tree"] == "clean"
    assert keys["source_script"] == "convert_lab_draft.py"


@pytest.mark.parametrize("invocation", ["relative", "absolute", "from the script's own directory"])
def test_the_script_url_does_not_depend_on_how_it_was_invoked(invocation, tmp_path, monkeypatch):
    """`sys.argv[0]` is verbatim what was typed, and git runs from the script's directory, not the caller's."""
    script = Path(make_repository(tmp_path / "conversions"))
    publish(tmp_path / "conversions")
    if invocation == "relative":
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["conversions/convert_lab.py"])
    elif invocation == "absolute":
        monkeypatch.setattr(sys, "argv", [str(script)])
    else:
        monkeypatch.chdir(script.parent)
        monkeypatch.setattr(sys, "argv", ["convert_lab.py"])

    commit = run_git(tmp_path / "conversions", "rev-parse", "HEAD")

    keys = parse_record(describe_source_script()[0])

    assert keys["source_script"] == f"https://github.com/lab/conversions/blob/{commit}/convert_lab.py"


def test_a_script_in_a_subdirectory_is_named_from_the_repository_root(tmp_path, monkeypatch):
    """The path describes the repository's own layout, which is not a leak, rather than the writer's disk."""
    make_repository(tmp_path / "conversions")
    script = tmp_path / "conversions" / "scripts" / "convert_lab.py"
    script.parent.mkdir()
    script.write_text("import lab_utils\n", encoding="utf-8")
    run_git(tmp_path / "conversions", "add", "scripts/convert_lab.py")
    run_git(tmp_path / "conversions", "commit", "--quiet", "--message", "move the conversion")
    monkeypatch.setattr(sys, "argv", [str(script)])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["source_script"] == "scripts/convert_lab.py"  # unpushed, so the path rather than a URL
    assert source_script_file_name == "convert_lab.py"
    assert str(tmp_path) not in source_script


def test_untracked_files_do_not_modify_the_working_tree(tmp_path, monkeypatch):
    """A conversion writes its output next to the script, which must not count as a modification."""
    script = make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    (tmp_path / "conversions" / "output.nwb").write_text("not really an NWB file", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["working_tree"] == "clean"
    assert keys["source_script"].startswith("https://")


def test_unpublished_commit_writes_no_script_url(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["working_tree"] == "clean"
    assert keys["commit_published"] == "no"
    assert keys["source_script"] == "convert_lab.py"


def test_script_outside_version_control(tmp_path, monkeypatch):
    script = tmp_path / "convert_lab.py"
    script.write_text("print('converting')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script)])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["version_control"] == "none"
    assert keys["source_script"] == "convert_lab.py"
    assert "repository" not in keys
    assert source_script_file_name == "convert_lab.py"


def test_a_machine_without_git(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    def no_git_binary(*arguments, **keyword_arguments):
        raise FileNotFoundError("git")

    monkeypatch.setattr(_provenance.subprocess, "run", no_git_binary)

    keys = parse_record(describe_source_script()[0])

    assert keys["version_control"] == "none"
    assert keys["source_script"] == "convert_lab.py"


def test_absolute_invocation_writes_no_path(tmp_path, monkeypatch):
    """``sys.argv[0]`` is verbatim what was typed, so an absolute invocation carries a home directory."""
    script = tmp_path / "somewhere" / "deep" / "convert_lab.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('converting')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script.absolute())])

    source_script, source_script_file_name = describe_source_script()

    assert str(tmp_path) not in source_script
    assert source_script_file_name == "convert_lab.py"


@pytest.mark.parametrize("argument", ["", "-c", "-"])
def test_interactive_session(argument, monkeypatch):
    monkeypatch.setattr(sys, "argv", [argument])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["execution_environment"] == "interactive"
    assert "source_script" not in keys
    assert source_script_file_name == "neuroconv"


def test_notebook_session(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["/environment/lib/site-packages/ipykernel_launcher.py", "-f", "kernel.json"])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["execution_environment"] == "notebook"
    assert "source_script" not in keys
    assert source_script_file_name == "neuroconv"


@pytest.mark.parametrize(
    "shell_name,expected_environment",
    [("ZMQInteractiveShell", "notebook"), ("TerminalInteractiveShell", "interactive")],
)
def test_a_live_ipython_shell(shell_name, expected_environment, monkeypatch):
    """
    IPython is not a dependency, so a real shell cannot be started here.

    What we own is the mapping from the shell IPython reports to the environment we record, which is
    what this pins. The branch where IPython is absent is covered by every other test in this file.
    """
    monkeypatch.setattr(sys, "argv", ["/environment/bin/ipython"])
    monkeypatch.setattr(_provenance, "_ipython_shell_name", lambda: shell_name)

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["execution_environment"] == expected_environment
    assert "source_script" not in keys
    assert source_script_file_name == "neuroconv"


def test_a_module_of_an_installed_library_is_not_the_conversion(tmp_path, monkeypatch):
    """``python -m some_library`` runs a script, but not the user's."""
    script = tmp_path / "site-packages" / "some_library" / "__main__.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('a library')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(script)])

    keys = parse_record(describe_source_script()[0])

    assert "source_script" not in keys
    assert "repository" not in keys


def test_console_entry_point_is_not_the_conversion(tmp_path, monkeypatch):
    """``neuroconv my_specification.yml`` runs our own wrapper, which is not a conversion script."""
    entry_point = tmp_path / "environment" / "bin" / "neuroconv"
    entry_point.parent.mkdir(parents=True)
    entry_point.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(entry_point)])

    source_script, source_script_file_name = describe_source_script()
    keys = parse_record(source_script)

    assert keys["execution_environment"] == "script"
    assert "source_script" not in keys
    assert source_script_file_name == "neuroconv"


def test_no_git_info_drops_the_git_keys(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    publish(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])
    monkeypatch.setenv("NEUROCONV_PROVENANCE", "no-git-info")

    keys = parse_record(describe_source_script()[0])

    assert keys["neuroconv_provenance_format"] == "1"
    assert keys["neuroconv_version"]
    assert keys["execution_environment"] == "script"
    assert keys["source_script"] == "convert_lab.py"
    assert not {"version_control", "repository", "commit", "working_tree", "commit_published"}.intersection(keys)


def test_no_git_info_runs_no_git_at_all(tmp_path, monkeypatch):
    """
    The switch is also the escape hatch out of the subprocesses.

    Everything git costs sits behind one guard, so turning the keys off turns the cost off with them
    rather than computing a record that is then discarded.
    """
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])
    monkeypatch.setenv("NEUROCONV_PROVENANCE", "no-git-info")

    def no_subprocess_expected(*arguments, **keyword_arguments):
        raise AssertionError(f"git was run despite the switch: {arguments}")

    monkeypatch.setattr(_provenance.subprocess, "run", no_subprocess_expected)

    keys = parse_record(describe_source_script()[0])

    assert keys["source_script"] == "convert_lab.py"
    assert "version_control" not in keys


def test_the_switch_is_read_on_every_call(tmp_path, monkeypatch):
    """
    The git description is cached, the switch is not.

    Caching one level higher would read the environment once per process, which is invisible in
    production and silently ignores every `monkeypatch.setenv` in this file.
    """
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    monkeypatch.setenv("NEUROCONV_PROVENANCE", "no-git-info")
    assert "version_control" not in parse_record(describe_source_script()[0])

    monkeypatch.setenv("NEUROCONV_PROVENANCE", "full-git-info")
    assert parse_record(describe_source_script()[0])["version_control"] == "git"


def test_full_git_info_is_the_default(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])
    monkeypatch.setenv("NEUROCONV_PROVENANCE", "full-git-info")

    assert parse_record(describe_source_script()[0])["repository"] == "https://github.com/lab/conversions"


def test_an_unrecognized_switch_discloses_less(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])
    monkeypatch.setenv("NEUROCONV_PROVENANCE", "full")  # a plausible typo

    assert "repository" not in parse_record(describe_source_script()[0])


@pytest.mark.parametrize(
    "remote,expected",
    [
        ("git@github.com:lab/conversions.git", "https://github.com/lab/conversions"),
        ("https://github.com/lab/conversions.git", "https://github.com/lab/conversions"),
        ("ssh://git@github.com/lab/conversions.git", "https://github.com/lab/conversions"),
        ("https://token:x-oauth-basic@github.com/lab/conversions.git", "https://github.com/lab/conversions"),
    ],
)
def test_remote_normalization(remote, expected, tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions", remote=remote)
    monkeypatch.setattr(sys, "argv", [script])

    assert parse_record(describe_source_script()[0])["repository"] == expected


def test_a_remote_that_is_a_local_path_is_not_written(tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions", remote=str(tmp_path / "elsewhere"))
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["version_control"] == "git"
    assert "repository" not in keys


@pytest.mark.parametrize(
    "remote,url_template",
    [
        ("git@github.com:lab/conversions.git", "https://github.com/lab/conversions/blob/{commit}/convert_lab.py"),
        ("git@gitlab.com:lab/conversions.git", "https://gitlab.com/lab/conversions/-/blob/{commit}/convert_lab.py"),
        (
            "git@bitbucket.org:lab/conversions.git",
            "https://bitbucket.org/lab/conversions/src/{commit}/convert_lab.py",
        ),
    ],
)
def test_the_url_layout_of_each_known_host(remote, url_template, tmp_path, monkeypatch):
    script = make_repository(tmp_path / "conversions", remote=remote)
    publish(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    commit = run_git(tmp_path / "conversions", "rev-parse", "HEAD")
    keys = parse_record(describe_source_script()[0])

    assert keys["source_script"] == url_template.format(commit=commit)


def test_an_unknown_host_states_the_commit_without_a_script_url(tmp_path, monkeypatch):
    """A remote names its host but not the software running on it, so a self-hosted forge is left out."""
    script = make_repository(tmp_path / "conversions", remote="git@git.institute.edu:lab/conversions.git")
    publish(tmp_path / "conversions")
    monkeypatch.setattr(sys, "argv", [script])

    keys = parse_record(describe_source_script()[0])

    assert keys["repository"] == "https://git.institute.edu/lab/conversions"
    assert keys["commit"]
    assert keys["source_script"] == "convert_lab.py"
