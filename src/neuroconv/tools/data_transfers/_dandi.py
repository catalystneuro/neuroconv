"""Collection of helper functions for assessing and performing automated data transfers for the DANDI archive."""

import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Optional, Union
from warnings import warn

from pydantic import DirectoryPath
from pynwb import NWBHDF5IO


def automatic_dandi_upload(
    dandiset_id: str,
    nwb_folder_path: DirectoryPath,
    dandiset_folder_path: Optional[DirectoryPath] = None,
    version: str = "draft",
    staging: bool = False,
    cleanup: bool = False,
    number_of_jobs: Union[int, None] = None,
    number_of_threads: Union[int, None] = None,
) -> list[Path]:
    """
    Fully automated upload of NWB files to a Dandiset.

    Requires an API token set as an environment variable named ``DANDI_API_KEY``.

    To set this in your bash terminal in Linux or macOS, run
        export DANDI_API_KEY=...
    or in Windows
        set DANDI_API_KEY=...

    DO NOT STORE THIS IN ANY PUBLICLY SHARED CODE.

    Parameters
    ----------
    dandiset_id : str
        Six-digit string identifier for the Dandiset the NWB files will be uploaded to.
    nwb_folder_path : folder path
        Folder containing the NWB files to be uploaded.
    dandiset_folder_path : folder path, optional
        A separate folder location within which to download the dandiset.
        Used in cases where you do not have write permissions for the parent of the 'nwb_folder_path' directory.
        Default behavior downloads the DANDISet to a folder adjacent to the 'nwb_folder_path'.
    version : str, default="draft"
        The version of the Dandiset to download. Even if no data has been uploaded yes, this step downloads an essential
        Dandiset metadata yaml file. Default is "draft", which is the latest state.
    staging : bool, default: False
        Is the Dandiset hosted on the staging server? This is mostly for testing purposes.
    cleanup : bool, default: False
        Whether to remove the Dandiset folder path and nwb_folder_path.
    number_of_jobs : int, optional
        The number of jobs to use in the DANDI upload process.
    number_of_threads : int, optional
        The number of threads to use in the DANDI upload process.
    """
    from dandi.download import download as dandi_download
    from dandi.organize import organize as dandi_organize
    from dandi.upload import upload as dandi_upload

    assert os.getenv("DANDI_API_KEY"), (
        "Unable to find environment variable 'DANDI_API_KEY'. "
        "Please retrieve your token from DANDI and set this environment variable."
    )

    dandiset_folder_path = (
        Path(mkdtemp(dir=nwb_folder_path.parent)) if dandiset_folder_path is None else dandiset_folder_path
    )
    dandiset_path = dandiset_folder_path / dandiset_id
    # Odd big of logic upstream: https://github.com/dandi/dandi-cli/blob/master/dandi/cli/cmd_upload.py#L92-L96
    if number_of_threads is not None and number_of_threads > 1 and number_of_jobs is None:
        number_of_jobs = -1

    url_base = "https://gui-staging.dandiarchive.org" if staging else "https://dandiarchive.org"
    dandiset_url = f"{url_base}/dandiset/{dandiset_id}/{version}"
    dandi_download(urls=dandiset_url, output_dir=str(dandiset_folder_path), get_metadata=True, get_assets=False)
    assert dandiset_path.exists(), "DANDI download failed!"

    # TODO: need PR on DANDI to expose number of jobs
    dandi_organize(
        paths=str(nwb_folder_path), dandiset_path=str(dandiset_path), devel_debug=True if number_of_jobs == 1 else False
    )
    organized_nwbfiles = dandiset_path.rglob("*.nwb")

    # DANDI has yet to implement forcing of session_id inclusion in organize step
    # This manually enforces it when only a single session per subject is organized
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

    organized_nwbfiles = [str(x) for x in dandiset_path.rglob("*.nwb")]
    # The above block can be removed once they add the feature

    assert len(list(dandiset_path.iterdir())) > 1, "DANDI organize failed!"

    dandi_instance = "dandi-staging" if staging else "dandi"  # Test

    dandi_upload(
        paths=organized_nwbfiles,
        dandi_instance=dandi_instance,
        jobs=number_of_jobs,
        jobs_per_file=number_of_threads,
    )

    # Cleanup should be confirmed manually; Windows especially can complain
    if cleanup:
        try:
            rmtree(path=dandiset_folder_path)
            rmtree(path=nwb_folder_path)
        except PermissionError:  # pragma: no cover
            warn("Unable to clean up source files and dandiset! Please manually delete them.")

    return organized_nwbfiles
