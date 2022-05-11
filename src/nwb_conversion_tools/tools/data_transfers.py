"""Collection of helper functions for assessing and performing automated data transfers."""
import os
import subprocess
import json
import re
from typing import Dict, Optional, List, Union, Tuple
from pathlib import Path
from warnings import warn
from shutil import rmtree
from time import sleep, time
from tempfile import mkdtemp

import psutil
from tqdm import tqdm
from pynwb import NWBHDF5IO
from dandi.download import download as dandi_download
from dandi.organize import organize as dandi_organize
from dandi.upload import upload as dandi_upload

from ..utils import FolderPathType, OptionalFolderPathType

try:  # pragma: no cover
    import globus_cli

    HAVE_GLOBUS = True
except ModuleNotFoundError:
    HAVE_GLOBUS = False


def _kill_process(proc):
    """Private helper for ensuring a process and any subprocesses are properly terminated after a timeout period."""
    try:
        process = psutil.Process(proc.pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()
    except psutil.NoSuchProcess:  # good process cleaned itself up
        pass


def deploy_process(command, catch_output: bool = False, timeout: Optional[float] = None):
    """Private helper for efficient submission and cleanup of shell processes."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, text=True)
    output = proc.communicate()[0].strip() if catch_output else None
    proc.wait(timeout=timeout)
    _kill_process(proc=proc)
    return output


def get_globus_dataset_content_sizes(
    globus_endpoint_id: str, path: str, recursive: bool = True, timeout: float = 120.0
) -> Dict[str, int]:  # pragma: no cover
    """
    May require external login via 'globus login' from CLI.

    Returns dictionary whose keys are file names and values are sizes in bytes.
    """
    assert HAVE_GLOBUS, "You must install the globus CLI (pip install globus-cli)!"

    recursive_flag = " --recursive" if recursive else ""
    contents = json.loads(
        deploy_process(
            command=f"globus ls -Fjson {globus_endpoint_id}:{path}{recursive_flag}", catch_output=True, timeout=timeout
        )
    )
    files_and_sizes = {item["name"]: item["size"] for item in contents["DATA"] if item["type"] == "file"}
    return files_and_sizes


def transfer_globus_content(
    source_endpoint_id: str,
    source_files: Union[str, List[List[str]]],
    destination_endpoint_id: str,
    destination_folder: FolderPathType,
    display_progress: bool = True,
    progress_update_rate: float = 60.0,
    progress_update_timeout: float = 600.0,
) -> Tuple[bool, List[str]]:  # pragma: no cover
    """
    Track progress for transferring content from source_endpoint_id to destination_endpoint_id:destination_folder.

    Parameters
    ----------
    source_endpoint_id : string
        Source Globus ID.
    source_files : string, or list of strings, or list of lists of strings
        A string path or list-of-lists of string paths of files to transfer from the source_endpoint_id.
        If using a nested list, the outer level indicates which requests will be batched together.
        If using a nested list, all items in a single batch level must be from the same common directory.

        It is recommended to transfer the largest file(s) with minimal batching,
        and to batch a large number of very small files together.

        It is also generally recommended to submit up to 3 simultaneous transfer,
        *i.e.*, `source_files` is recommended to have at most 3 items all of similar total byte size.
    destination_endpoint_id : string
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
        Returns the total status of all transfers when they either finish or the progress tracking times out.
    task_ids : list of strings
        List of the task IDs submitted to globus, if further information is needed to reestablish tracking or terminate.
    """

    def _submit_transfer_request(
        source_endpoint_id: str,
        source_files: Union[str, List[List[str]]],
        destination_endpoint_id: str,
        destination_folder_path: Path,
    ) -> Dict[str, int]:
        """Send transfer request to Globus."""
        folder_content_sizes = dict()
        task_total_sizes = dict()
        for j, batched_source_files in enumerate(source_files):
            paths_file = destination_folder_path / f"paths_{j}.txt"
            # .as_posix() to ensure correct string form Globus expects
            # ':' replacement for Windows drives
            source_folder = Path(batched_source_files[0]).parent.as_posix().replace(":", "")
            destination_folder_name = destination_folder_path.as_posix().replace(":", "")
            with open(file=paths_file, mode="w") as f:
                for source_file in batched_source_files:
                    file_name = Path(source_file).name
                    f.write(f"{file_name} {file_name}\n")

            transfer_command = (
                "globus transfer "
                f"{source_endpoint_id}:{source_folder} {destination_endpoint_id}:/{destination_folder_name} "
                f"--batch {paths_file}"
            )
            transfer_message = deploy_process(
                command=transfer_command,
                catch_output=True,
            )
            task_id = re.findall(
                pattern=(
                    "^Message: The transfer has been accepted and a task has been created and queued for "
                    "execution\nTask ID: (.+)$"
                ),
                string=transfer_message,
            )
            paths_file.unlink()
            assert task_id, f"Transfer submission failed! Globus output:\n{transfer_message}."

            if source_folder not in folder_content_sizes:
                contents = get_globus_dataset_content_sizes(globus_endpoint_id=source_endpoint_id, path=source_folder)
                folder_content_sizes.update({source_folder: contents})
            task_total_sizes.update(
                {
                    task_id[0]: sum(
                        [
                            folder_content_sizes[source_folder][Path(source_file).name]
                            for source_file in batched_source_files
                        ]
                    )
                }
            )
        return task_total_sizes

    def _track_transfer(
        task_total_sizes: Dict[str, int],
        display_progress: bool = True,
        progress_update_rate: float = 60.0,
        progress_update_timeout: float = 600.0,
    ) -> bool:
        """Track the progress of transfers."""
        if display_progress:
            all_pbars = [
                tqdm(desc=f"Transferring batch #{j}...", total=total_size, position=j, leave=True)
                for j, total_size in enumerate(task_total_sizes.values(), start=1)
            ]
        all_status = [False for _ in task_total_sizes]
        success = all(all_status)
        time_so_far = 0.0
        start_time = time()
        while not success and time_so_far <= progress_update_timeout:
            time_so_far = time() - start_time
            for j, (task_id, task_total_size) in enumerate(task_total_sizes.items()):
                task_update = deploy_process(f"globus task show {task_id} -Fjson", catch_output=True)
                task_message = json.loads(task_update)
                all_status[j] = task_message["status"] == "SUCCEEDED"
                assert (
                    all_status[j] != "OK" or all_status[j] != "SUCCEEDED"
                ), f"Something went wrong with the transfer! Please manually inspect the task with ID '{task_id}'."
                if display_progress:
                    all_pbars[j].update(n=task_message["bytes_transferred"] - all_pbars[j].n)
            success = all(all_status)
            if not success:
                sleep(progress_update_rate)
        return success

    source_files = [[source_files]] if isinstance(source_files, str) else source_files
    destination_folder_path = Path(destination_folder)
    destination_folder_path.mkdir(exist_ok=True)
    # assertion check is ensure the logical iteration does not occur over the individual string values
    assert (
        isinstance(source_files, list) and source_files and isinstance(source_files[0], list) and source_files[0]
    ), "'source_files' must be a non-empty nested list-of-lists to indicate batched transfers!"
    assert destination_folder_path.is_absolute(), (
        "The 'destination_folder' must be an absolute path to resolve ambiguity with relative Globus head "
        "as well as avoiding Globus access permissions to a personal relative path!"
    )

    task_total_sizes = _submit_transfer_request(
        source_endpoint_id=source_endpoint_id,
        source_files=source_files,
        destination_endpoint_id=destination_endpoint_id,
        destination_folder_path=destination_folder_path,
    )
    success = _track_transfer(
        task_total_sizes=task_total_sizes,
        display_progress=display_progress,
        progress_update_rate=progress_update_rate,
        progress_update_timeout=progress_update_timeout,
    )
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


def automatic_dandi_upload(
    dandiset_id: str,
    nwb_folder_path: FolderPathType,
    dandiset_folder_path: OptionalFolderPathType = None,
    version: Optional[str] = None,
    staging: bool = False,
    cleanup: bool = False,
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
    cleanup : bool, optional
        Whether or not to remove the dandiset folder path and nwb_folder_path.
        Defaults to False.
    """
    dandiset_folder_path = (
        Path(mkdtemp(dir=nwb_folder_path.parent)) if dandiset_folder_path is None else dandiset_folder_path
    )
    dandiset_path = dandiset_folder_path / dandiset_id
    version = "draft" if version is None else version
    assert os.getenv("DANDI_API_KEY"), (
        "Unable to find environment variable 'DANDI_API_KEY'. "
        "Please retrieve your token from DANDI and set this environment variable."
    )

    url_base = "https://gui-staging.dandiarchive.org" if staging else "https://dandiarchive.org"
    dandiset_url = f"{url_base}/dandiset/{dandiset_id}/{version}"
    dandi_download(urls=dandiset_url, output_dir=str(dandiset_folder_path), get_metadata=True, get_assets=False)
    assert dandiset_path.exists(), "DANDI download failed!"

    dandi_organize(paths=str(nwb_folder_path), dandiset_path=str(dandiset_path))
    organized_nwbfiles = dandiset_path.rglob("*.nwb")

    # DANDI has yet to implement forcing of session_id inclusion in organize step
    # This manually enforces it when only a single sesssion per subject is organized
    for organized_nwbfile in organized_nwbfiles:
        if "ses" not in organized_nwbfile.stem:
            with NWBHDF5IO(path=organized_nwbfile, mode="r") as io:
                nwbfile = io.read()
                session_id = nwbfile.session_id
            dandi_stem = organized_nwbfile.stem
            dandi_stem_split = dandi_stem.split("_")
            dandi_stem_split.insert(1, f"ses-{session_id}")
            corrected_name = "_".join(dandi_stem_split) + ".nwb"
            organized_nwbfile.rename(organized_nwbfile.parent / corrected_name)
    organized_nwbfiles = dandiset_path.rglob("*.nwb")
    # The above block can be removed once they add the feature

    assert len(list(dandiset_path.iterdir())) > 1, "DANDI organize failed!"

    dandi_instance = "dandi-staging" if staging else "dandi"
    dandi_upload(paths=[str(x) for x in organized_nwbfiles], dandi_instance=dandi_instance)

    # Cleanup should be confirmed manually; Windows especially can complain
    if cleanup:
        try:
            rmtree(path=dandiset_folder_path)
            rmtree(path=nwb_folder_path)
        except PermissionError:  # pragma: no cover
            warn("Unable to clean up source files and dandiset! Please manually delete them.")
