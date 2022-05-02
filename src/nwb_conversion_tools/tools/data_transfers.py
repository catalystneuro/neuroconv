"""Collection of helper functions for assessing and performing automated data transfers."""
import os
import subprocess
import json
import re
from typing import Dict, Optional
from pathlib import Path
from warnings import warn
from shutil import rmtree

import psutil

from ..utils import FolderPathType, OptionalFolderPathType

try:  # pragma: no cover
    import globus_cli

    HAVE_GLOBUS = True
except ModuleNotFoundError:
    HAVE_GLOBUS = False


def _kill_process(proc, timeout: Optional[float] = None):
    """Private helper for ensuring a process and any subprocesses are properly terminated after a timeout period."""

    def _kill(proc):
        """Local helper for ensuring a process and any subprocesses are properly terminated."""
        try:
            process = psutil.Process(proc.pid)
            for proc in process.children(recursive=True):
                proc.kill()
            process.kill()
        except psutil.NoSuchProcess:  # good process cleaned itself up
            pass

    try:
        proc.wait(timeout=timeout)
        _kill(proc=proc)
    except subprocess.TimeoutExpired:
        _kill(proc=proc)


def _deploy_process(command, catch_output: bool = False, timeout: Optional[float] = None):
    """Private helper for efficient submission and cleanup of shell processes."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, text=True)
    output = proc.communicate()[0].strip() if catch_output else None
    if timeout is not None:
        _kill_process(proc=proc, timeout=timeout)
    return output


def get_globus_dataset_content_sizes(
    globus_endpoint_id: str, path: str, recursive: bool = True, timeout: float = 120.0
) -> Dict[str, int]:
    """
    May require external login via 'globus login' from CLI.

    Returns dictionary whose keys are file names and values are sizes in bytes.
    """
    assert HAVE_GLOBUS, "You must install the globus CLI (pip install globus-cli)!"

    recursive_flag = " --recursive" if recursive else ""
    contents = json.loads(
        _deploy_process(
            command=f"globus ls -Fjson {globus_endpoint_id}:{path}{recursive_flag}", catch_output=True, timeout=timeout
        )
    )
    files_and_sizes = {item["name"]: item["size"] for item in contents["DATA"] if item["type"] == "file"}
    return files_and_sizes


def estimate_total_conversion_runtime(
    total_mb: float,
    transfer_rate_mb: float = 20.0,
    conversion_rate_mb: float = 17.0,
    upload_rate_mb: float = 40,
    compression_ratio: float = 1.7,
):
    """
    Estimate how long the combined process of data transfer, conversion, and upload is expected to take.

    Parameters
    ----------
    total_mb: float
        The total amount of data (in MB) that will be transferred, converted, and uploaded to dandi.
    transfer_rate_mb: float, optional
        Estimate of the transfer rate for the data.
    conversion_rate_mb: float, optional
        Estimate of the conversion rate for the data. Can vary widely depending on conversion options and type of data.
        Figure of 17MB/s is based on extensive compression of high-volume, high-resolution ecephys.
    upload_rate_mb: float, optional
        Estimate of the upload rate of a single file to the DANDI archive.
    compression_ratio: float, optional
        Esimate of the final average compression ratio for datasets in the file. Can vary widely.
    """
    c = 1 / compression_ratio  # compressed_size = total_size * c
    return total_mb * (1 / transfer_rate_mb + 1 / conversion_rate_mb + c / upload_rate_mb)


def estimate_s3_conversion_cost(
    total_mb: float,
    transfer_rate_mb: float = 20.0,
    conversion_rate_mb: float = 17.0,
    upload_rate_mb: float = 40,
    compression_ratio: float = 1.7,
):
    """
    Estimate potential cost of performing an entire conversion on S3 using full automation.

    Parameters
    ----------
    total_mb: float
        The total amount of data (in MB) that will be transferred, converted, and uploaded to dandi.
    transfer_rate_mb: float, optional
        Estimate of the transfer rate for the data.
    conversion_rate_mb: float, optional
        Estimate of the conversion rate for the data. Can vary widely depending on conversion options and type of data.
        Figure of 17MB/s is based on extensive compression of high-volume, high-resolution ecephys.
    upload_rate_mb: float, optional
        Estimate of the upload rate of a single file to the DANDI archive.
    compression_ratio: float, optional
        Esimate of the final average compression ratio for datasets in the file. Can vary widely.
    """
    c = 1 / compression_ratio  # compressed_size = total_size * c
    total_mb_s = (
        total_mb**2 / 2 * (1 / transfer_rate_mb + (2 * c + 1) / conversion_rate_mb + 2 * c**2 / upload_rate_mb)
    )
    cost_gb_m = 0.08 / 1e3  # $0.08 / GB Month
    cost_mb_s = cost_gb_m / (1e3 * 2.628e6)  # assuming 30 day month; unsure how amazon weights shorter months?
    return cost_mb_s * total_mb_s


def dandi_upload(
    dandiset_id: str,
    nwb_folder_path: FolderPathType,
    dandiset_folder_path: OptionalFolderPathType = None,
    version: Optional[str] = None,
    staging: bool = False,
    process_timeouts: Optional[Dict[str, Optional[float]]] = None,
):
    """
    Fully automated upload of NWBFiles to a DANDISet.

    Requires an API token set as an envrinment variable named DANDI_API_KEY.

    To set this in your bash terminal in Linux or MacOS, run
        export DANDI_API_KEY="..."
    or in Windows
        set DANDI_API_KEY="..."

    DO NOT STORE THIS IN ANY PUBLICLY SHARED CODE.

    Parameters
    ----------
    dandiset_id : str
        Six-digit string identifier for the DANDISet the NWBFiles will be uploaded to.
    nwb_folder_path : folder path
        Folder containing the NWBFiles to be uploaded.
    dandiset_folder_path : folder path, optional
        A separate folder location within which to download the dandiset.
        Used in cases where you do not have write permissions for the parent of the 'nwb_folder_path' directory.
        Default behavior downloads the DANDISet to a folder adjacent to the 'nwb_folder_path'.
    version : str, optional
        "draft" or "version".
        The default is "draft".
    staging : bool, optional
        Is the DANDISet hosted on the staging server? This is mostly for testing purposes.
        The default is False.
    process_timeouts : Dict[str, Optional[float]], optional
        Dictionary used to specify mazimum timeout of each individual process in the DANDI upload.
        Keys must be from ['validate', 'download', 'organize', 'upload'].
        The value of each key is number of seconds to wait before forcibly terminating.
        Set any value to None to wait until the process completes, however long that may be.
        The default is for all processes except organize to wait until full completion
        (in testing, organize subprocess doesn't seem to want to wait successfully).
    """
    initial_wd = os.getcwd()
    dandiset_folder_path = nwb_folder_path.parent if dandiset_folder_path is None else dandiset_folder_path
    version = "draft" if version is None else version
    process_timeouts = dict() if process_timeouts is None else process_timeouts
    assert os.getenv("DANDI_API_KEY"), (
        "Unable to find environment variable 'DANDI_API_KEY'. "
        "Please retrieve your token from DANDI and set this environment variable."
    )
    url_base = "https://gui-staging.dandiarchive.org" if staging else "https://dandiarchive.org"
    dandiset_url = f"{url_base}/dandiset/{dandiset_id}/{version}"

    os.chdir(nwb_folder_path.parent)
    validate_return = _deploy_process(
        command=f"dandi validate {nwb_folder_path.name}",
        catch_output=True,
        timeout=process_timeouts.get("validate"),
    )
    assert re.fullmatch(
        pattern=r"^Summary: No validation errors among \d+ file\(s\)$", string=validate_return
    ), "DANDI validation failed!"

    os.chdir(dandiset_folder_path)
    download_return = _deploy_process(
        command=f"dandi download {dandiset_url} --download dandiset.yaml",
        catch_output=True,
        timeout=process_timeouts.get("download"),
    )
    assert download_return, "DANDI download failed!"  # output is a bit too dynamic to regex; if it fails it is empty

    os.chdir(dandiset_folder_path / dandiset_id)
    _deploy_process(
        command=f"dandi organize {nwb_folder_path.absolute()}",  # .absolute() needed if dandiset folder is elsewhere
        timeout=process_timeouts.get("organize", 120.0),
    )
    assert len(list(Path.cwd().iterdir())) > 1, "DANDI organize failed!"

    dandi_upload_command = "dandi upload -i dandi-staging" if staging else "dandi upload"
    upload_return = _deploy_process(
        command=dandi_upload_command, catch_output=True, timeout=process_timeouts.get("upload")
    )
    assert upload_return, "DANDI upload failed!"

    # cleanup - should be confirmed manually, Windows especially can complain
    os.chdir(initial_wd)  # restore to initial working directory; also to prevent additional process usage permissions
    try:
        rmtree(path=nwb_folder_path.parent / dandiset_id)
        rmtree(path=nwb_folder_path)
    except PermissionError:
        warn("Unable to clean up source files and dandiset! Please manually delete them.")
