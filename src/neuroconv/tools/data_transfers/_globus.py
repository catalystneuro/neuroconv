"""Collection of helper functions for assessing and performing automated data transfers."""

import json
import re
from pathlib import Path
from time import sleep, time
from typing import Union

from pydantic import DirectoryPath
from tqdm import tqdm

from ..importing import is_package_installed
from ..processes import deploy_process


def get_globus_dataset_content_sizes(
    globus_endpoint_id: str, path: str, recursive: bool = True, timeout: float = 120.0
) -> dict[str, int]:  # pragma: no cover
    """
    May require external login via 'globus login' from CLI.

    Returns dictionary whose keys are file names and values are sizes in bytes.
    """
    assert is_package_installed(package_name="globus_cli"), "You must install the globus CLI (pip install globus-cli)!"

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
    source_files: Union[str, list[list[str]]],
    destination_endpoint_id: str,
    destination_folder: DirectoryPath,
    display_progress: bool = True,
    progress_update_rate: float = 60.0,
    progress_update_timeout: float = 600.0,
) -> tuple[bool, list[str]]:  # pragma: no cover
    """
    Track progress for transferring content from source_endpoint_id to destination_endpoint_id:destination_folder.

    Parameters
    ----------
    source_endpoint_id : str
        Source Globus ID.
    source_files : string, or list of strings, or list of lists of strings
        A string path or list-of-lists of string paths of files to transfer from the source_endpoint_id.
        If using a nested list, the outer level indicates which requests will be batched together.
        If using a nested list, all items in a single batch level must be from the same common directory.

        It is recommended to transfer the largest file(s) with minimal batching,
        and to batch a large number of very small files together.

        It is also generally recommended to submit up to 3 simultaneous transfer,
        *i.e.*, `source_files` is recommended to have at most 3 items all of similar total byte size.
    destination_endpoint_id : str
        Destination Globus ID.
    destination_folder : FolderPathType
        Absolute path to a local folder where all content will be transferred to.
    display_progress : bool, default: True
        Whether to display the transfer as progress bars using `tqdm`.
    progress_update_rate : float, default: 60.0
        How frequently (in seconds) to update the progress bar display tracking the data transfer.
    progress_update_timeout : float, default: 600.0
        Maximum amount of time to monitor the transfer progress.
        You may wish to set this to be longer when transferring very large files.

    Returns
    -------
    success : bool
        Returns the total status of all transfers when they either finish or the progress tracking times out.
    task_ids : list of strings
        List of the task IDs submitted to globus, if further information is needed to reestablish tracking or terminate.
    """

    def _submit_transfer_request(
        source_endpoint_id: str,
        source_files: Union[str, list[list[str]]],
        destination_endpoint_id: str,
        destination_folder_path: Path,
    ) -> dict[str, int]:
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
        task_total_sizes: dict[str, int],
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
