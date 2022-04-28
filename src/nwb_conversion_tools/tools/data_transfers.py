"""Collection of helper functions for assessing and performing automated data transfers."""
import os
import json
from typing import Dict

try:  # pragma: no cover
    import globus_cli

    HAVE_GLOBUS = True
except ModuleNotFoundError:
    HAVE_GLOBUS = False


def get_globus_dataset_content_sizes(globus_endpoint_id: str, path: str, recursive: bool = True) -> Dict[str, int]:
    """
    May require external login via 'globus login' from CLI.

    Returns dictionary whose keys are file names and values are sizes in bytes.
    """
    assert HAVE_GLOBUS, "You must install the globus CLI (pip install globus-cli)!"

    recursive_flag = " --recursive" if recursive else ""
    contents = json.loads(os.popen(f"globus ls -Fjson {globus_endpoint_id}:{path}{recursive_flag}").read())
    files_and_sizes = {item["name"]: item["size"] for item in contents["DATA"] if item["type"] == "file"}
    return files_and_sizes
