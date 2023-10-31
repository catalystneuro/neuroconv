import os
import sys
from datetime import datetime
from pathlib import Path
from platform import python_version as get_python_version
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.tools.data_transfers import automatic_dandi_upload
from neuroconv.tools.nwb_helpers import (
    get_default_nwbfile_metadata,
    make_nwbfile_from_metadata,
)

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
        metadata["NWBFile"].update(
            session_start_time=datetime.now().astimezone(),
            session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}",
        )
        metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
        with NWBHDF5IO(path=self.nwb_folder_path / "test_nwb_1.nwb", mode="w") as io:
            io.write(make_nwbfile_from_metadata(metadata=metadata))

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_automatic_dandi_upload(self):
        automatic_dandi_upload(dandiset_id="200560", nwb_folder_path=self.nwb_folder_path, staging=True)


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_API_KEY to run this test!",
)
class TestAutomaticDANDIUploadNonParallel(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())
        self.nwb_folder_path = self.tmpdir / "test_nwb"
        self.nwb_folder_path.mkdir()
        metadata = get_default_nwbfile_metadata()
        metadata["NWBFile"].update(
            session_start_time=datetime.now().astimezone(),
            session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}",
        )
        metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
        with NWBHDF5IO(path=self.nwb_folder_path / "test_nwb_2.nwb", mode="w") as io:
            io.write(make_nwbfile_from_metadata(metadata=metadata))

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_automatic_dandi_upload_non_parallel(self):
        automatic_dandi_upload(
            dandiset_id="200560", nwb_folder_path=self.nwb_folder_path, staging=True, number_of_jobs=1
        )


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_API_KEY to run this test!",
)
class TestAutomaticDANDIUploadNonParallelNonThreaded(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())
        self.nwb_folder_path = self.tmpdir / "test_nwb"
        self.nwb_folder_path.mkdir()
        metadata = get_default_nwbfile_metadata()
        metadata["NWBFile"].update(
            session_start_time=datetime.now().astimezone(),
            session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}",
        )
        metadata.update(Subject=dict(subject_id="foo", species="Mus musculus", age="P1D", sex="U"))
        with NWBHDF5IO(path=self.nwb_folder_path / "test_nwb_3.nwb", mode="w") as io:
            io.write(make_nwbfile_from_metadata(metadata=metadata))

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_automatic_dandi_upload_non_parallel_non_threaded(self):
        automatic_dandi_upload(
            dandiset_id="200560",
            nwb_folder_path=self.nwb_folder_path,
            staging=True,
            number_of_jobs=1,
            number_of_threads=1,
        )
