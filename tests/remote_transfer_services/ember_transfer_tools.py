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

EMBER_API_KEY = os.getenv("EMBER_API_KEY")
HAVE_EMBER_KEY = EMBER_API_KEY is not None and EMBER_API_KEY != ""  # can be "" from external forks


@pytest.mark.skipif(
    not HAVE_EMBER_KEY,
    reason="You must set your EMBER_API_KEY to run this test!",
)
def test_automatic_ember_upload(tmp_path, monkeypatch):
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

    # Note: It is not a valid usage to have a shell that contains both DANDI_API_KEY and EMBER_API_KEY
    # So in the tests we will ensure that only the appropriate one is set at runtime
    DANDI_API_KEY_PRESENT = "DANDI_API_KEY" in os.environ
    DANDI_SANDBOX_API_KEY_PRESENT = "DANDI_SANDBOX_API_KEY" in os.environ
    if DANDI_API_KEY_PRESENT:
        DANDI_API_KEY = os.environ.pop(key="DANDI_API_KEY")
    if DANDI_SANDBOX_API_KEY_PRESENT:
        DANDI_SANDBOX_API_KEY = os.environ.pop(key="DANDI_SANDBOX_API_KEY")

    # Some systems and setups (mostly CI) have trouble passing the env variable to the keyring; just mimic user input
    monkeypatch.setattr("getpass.getpass", lambda _: EMBER_API_KEY)
    monkeypatch.setattr("builtins.input", lambda _: EMBER_API_KEY)
    automatic_dandi_upload(dandiset_id="000431", nwb_folder_path=nwb_folder_path, instance="ember")

    # Restore the environment variable in case any other tests in this session need it
    if DANDI_API_KEY_PRESENT:
        os.environ["DANDI_API_KEY"] = DANDI_API_KEY
    if DANDI_SANDBOX_API_KEY_PRESENT:
        os.environ["DANDI_SANDBOX_API_KEY"] = DANDI_SANDBOX_API_KEY
