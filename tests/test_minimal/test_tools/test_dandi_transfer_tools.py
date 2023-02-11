import os
import sys
from datetime import datetime
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree
from platform import python_version as get_python_version

import pytest
from pynwb import NWBHDF5IO
from hdmf.testing import TestCase

from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata, get_default_nwbfile_metadata
from neuroconv.tools.data_transfers import automatic_dandi_upload

DANDI_API_KEY = os.getenv("DANDI_API_KEY")
HAVE_DANDI_KEY = DANDI_API_KEY is not None and DANDI_API_KEY != ""  # can be "" from external forks


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_API_KEY to run this test!",
)
class TestAutomaticDANDIUpload(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())
        self.nwb_folder_path = self.tmpdir / "test_nwb"
        self.nwb_folder_path.mkdir()
        metadata = get_default_nwbfile_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone(), session_id=f"test-automatic-upload-{sys.platform}-{get_python_version()}")
        metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
        with NWBHDF5IO(path=self.nwb_folder_path / "test_nwb_1.nwb", mode="w") as io:
            io.write(make_nwbfile_from_metadata(metadata=metadata))

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_automatic_dandi_upload(self):
        automatic_dandi_upload(dandiset_id="200560", nwb_folder_path=self.nwb_folder_path, staging=True)
