"""Collection of helper functions for assessing and performing automated data transfers."""
import os
import subprocess
import json
import re
from typing import Dict, Optional, List, Union
from pathlib import Path
from warnings import warn
from shutil import rmtree
from time import sleep, time

import psutil
from tqdm import tqdm

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


def transfer_globus_content(
    source_id: str,
    source_files: Union[str, List[List[str]]],
    destination_id: str,
    destination_folder: FolderPathType,
    display_progress: bool = True,
    progress_update_rate: float = 60.0,
    progress_update_timeout: float = 600.0,
) -> (bool, List[str]):
    """
    Track download progress for transferring content from source_id to destination_id:destination_folder.

    Parameters
    ----------
    source_id : string
        Source Globus ID.
    source_files : string, or list of strings, or list of lists of strings
        A string path or list-of-lists of string paths of files to transfer from the source_id.
        If using a nested list, the outer level indicates which requests will be batched together.
        If using a nested list, all items in a single batch level must be from the same common directory.

        It is recommended to transfer the largest file(s) with minimal batching,
        and to batch a large number of very small files together.

        It is also generally recommended to submit up to 3 simultaneous transfer,
        *i.e.*, `source_files` is recommended to have at most 3 items all of similar total byte size.
    destination_id : string
        Destination Globus ID.
    destination_folder : FolderPathType
        Absolute path to a local folder where all content will be transfered to.
    display_progress : bool, optional
        Whether or not to display the transfer as progress bars using `tqdm`.
        Defaults to True.
    progress_update_rate : float, optional
        How frequently (in seconds) to update the progress bar display tracking the data transfer.
        Defaults to 30 seconds.
    progress_update_tiemout : float, optional
        Maximum amount of time to monitor the transfer progress.
        You may wish to set this to be longer when transferring very large files.
        Defaults to 10 minutes.

    Returns
    -------
    success : bool
        If 'display_progress'=False, and the transfer was succesfully initiated, then this function returns True.

        If 'display_progress'=True (the default), then this function returns the total status of all transfers
        when they either finish or the progress tracking times out.
    task_ids : list of strings
        List of the task IDs submitted to globus, if further information is needed to reestablish tracking or terminate.
    """
    source_files = [[source_files]] if isinstance(source_files, str) else source_files
    # assertion check is ensure the logical iteration does not occur over the individual string values
    assert (
        isinstance(source_files, list) and source_files and isinstance(source_files[0], list) and source_files[0]
    ), "'source_files' must be a non-empty nested list-of-lists to indicate batched transfers!"
    assert destination_folder.is_absolute(), (
        "The 'destination_folder' must be an absolute path to resolve ambiguity with relative Globus head "
        "as well as avoiding Globus access permissions to a personal relative path!"
    )

    folder_content_sizes = dict()
    task_total_sizes = dict()
    for j, batched_source_files in enumerate(source_files):
        paths_file = Path(destination_folder) / f"paths_{j}.txt"
        # .as_posix() to ensure correct string form Globus expects
        # ':' replacement for Windows drives
        source_folder = Path(batched_source_files[0]).parent.as_posix().replace(":", "")
        destination_folder_name = Path(destination_folder).as_posix().replace(":", "")
        with open(file=paths_file, mode="w") as f:
            for source_file in batched_source_files:
                file_name = Path(source_file).name
                f.write(f"{file_name} {file_name}\n")

        transfer_message = _deploy_process(
            command=(
                f"globus transfer {source_id}:{source_folder} {destination_id}:{destination_folder_name} "
                f"--batch {paths_file}"
            ),
            catch_output=True,
        )
        task_id = re.findall(
            pattern=(
                "^Message: The transfer has been accepted and a task has been created and queued for "
                "execution\nTask ID: (.+)\n$"
            ),
            string=transfer_message,
        )
        assert task_id is not None, "Transfer submission failed! Globus output:\n{transfer_message}."
        # paths_file.unlink()

        if source_folder not in folder_content_sizes:
            contents = get_globus_dataset_content_sizes(globus_endpoint_id=source_id, path=source_folder)
            folder_content_sizes.update(contents)
        task_total_sizes.update(
            {task_id: sum([folder_content_sizes[source_folder][source_file] for source_file in batched_source_files])}
        )

    success = True
    if display_progress:
        all_pbars = [
            tqdm(desc=f"Transferring batch #{j}...", total=total_size, position=j, leave=True)
            for j, total_size in enumerate(task_total_sizes.values())
        ]
        all_status = [False for _ in task_total_sizes]
        success = all(all_status)
        time_so_far = 0.0
        start_time = time()
        while not success and time_so_far <= progress_update_timeout:
            time_so_far = time() - start_time
            for j, (task_id, task_total_size) in enumerate(task_total_sizes.items()):
                task_message = json.loads(_deploy_process(f"globus task show {task_id}", catch_output=True))
                all_status[j] = task_message["status"] == "SUCCEEDED"
                all_pbars[j].update(n=task_message["bytes_transferred"])
            sleep(secs=progress_update_rate)
    return success, list(task_total_sizes)


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
