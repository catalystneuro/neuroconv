import os
import sys
from datetime import datetime
from platform import python_version as get_python_version

import pytest
from pynwb import NWBHDF5IO

from neuroconv.tools.data_transfers import automatic_dandi_upload
from neuroconv.tools.nwb_helpers import (
    get_default_nwbfile_metadata,
    make_nwbfile_from_metadata,
)

DANDI_API_KEY = os.getenv("DANDI_API_KEY")
EMBER_API_KEY = os.getenv("EMBER_API_KEY")
HAVE_DANDI_KEY = DANDI_API_KEY is not None and DANDI_API_KEY != ""  # can be "" from external forks
HAVE_EMBER_KEY = EMBER_API_KEY is not None and EMBER_API_KEY != ""  # can be "" from external forks


def test_automatic_dandi_upload(tmp_path):
    nwb_folder_path = tmp_path / "test_nwb"
    nwb_folder_path.mkdir()
    metadata = get_default_nwbfile_metadata()
    metadata["NWBFile"].update(
        session_start_time=datetime.now().astimezone(),
        session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}",
    )
    metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
    with NWBHDF5IO(path=nwb_folder_path / "test_nwb_1.nwb", mode="w") as io:
        io.write(make_nwbfile_from_metadata(metadata=metadata))

    automatic_dandi_upload(dandiset_id="200560", nwb_folder_path=nwb_folder_path, sandbox=True)


def test_automatic_dandi_upload_non_parallel(tmp_path):
    nwb_folder_path = tmp_path / "test_nwb"
    nwb_folder_path.mkdir()
    metadata = get_default_nwbfile_metadata()
    metadata["NWBFile"].update(
        session_start_time=datetime.now().astimezone(),
        session_id=(f"test-automatic-upload-{sys.platform}-" f"{get_python_version().replace('.', '-')}-non-parallel"),
    )
    metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
    with NWBHDF5IO(path=nwb_folder_path / "test_nwb_2.nwb", mode="w") as io:
        io.write(make_nwbfile_from_metadata(metadata=metadata))

    automatic_dandi_upload(dandiset_id="200560", nwb_folder_path=nwb_folder_path, sandbox=True, number_of_jobs=1)


def test_automatic_dandi_upload_non_parallel_non_threaded(tmp_path):
    nwb_folder_path = tmp_path / "test_nwb"
    nwb_folder_path.mkdir()
    metadata = get_default_nwbfile_metadata()
    metadata["NWBFile"].update(
        session_start_time=datetime.now().astimezone(),
        session_id=(
            f"test-automatic-upload-{sys.platform}-"
            f"{get_python_version().replace('.', '-')}-non-parallel-non-threaded"
        ),
    )
    metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
    with NWBHDF5IO(path=nwb_folder_path / "test_nwb_3.nwb", mode="w") as io:
        io.write(make_nwbfile_from_metadata(metadata=metadata))

    automatic_dandi_upload(
        dandiset_id="200560",
        nwb_folder_path=nwb_folder_path,
        sandbox=True,
        number_of_jobs=1,
        number_of_threads=1,
    )


def test_staging_sandbox_conflict(tmp_path):
    """Test that providing both 'staging' and 'sandbox' parameters raises ValueError."""

    nwb_folder_path = tmp_path / "test_nwb"
    nwb_folder_path.mkdir()

    with pytest.raises(ValueError, match="Cannot specify both 'staging' and 'sandbox' parameters"):
        automatic_dandi_upload(dandiset_id="200000", nwb_folder_path=nwb_folder_path, sandbox=True, staging=True)
