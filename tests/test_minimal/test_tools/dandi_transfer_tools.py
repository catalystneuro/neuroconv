import os
import sys
from datetime import datetime
from pathlib import Path
from platform import python_version as get_python_version
from shutil import rmtree
from tempfile import mkdtemp

import dandi.dandiapi
import pytest
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv import run_conversion_from_yaml
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
            session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}-non-parallel",
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
            session_id=f"test-automatic-upload-{sys.platform}-{get_python_version().replace('.', '-')}-non-parallel-non-threaded",
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


def test_run_conversion_from_yaml_with_dandi_upload():
    path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
    yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_dandi_upload.yml"
    run_conversion_from_yaml(
        specification_file_path=yaml_file_path,
        data_folder_path=DATA_PATH,
        output_folder_path=OUTPUT_PATH,
        overwrite=True,
    )

    time.sleep(20)  # Give some buffer room for server to process before making assertions against DANDI API

    client = dandi.dandiapi.DandiAPIClient(api_url="https://api-staging.dandiarchive.org/api")
    dandiset = client.get_dandiset("200560")

    expected_asset_paths = [
        "sub-yaml-1/sub-yaml-1_ses-test-yaml-1_ecephys.nwb",
        "sub-yaml-002/sub-yaml-002_ses-test-yaml-2_ecephys.nwb",
        "sub-YAML-Subject-Name/sub-YAML-Subject-Name_ses-test-yaml-3_ecephys.nwb",
    ]
    for asset_path in expected_asset_paths:
        test_asset = dandiset.get_asset_by_path(path=asset_path)  # Will error if not found
        test_asset_metadata = test_asset.get_raw_metadata()

        # Past uploads may have created the same apparent file, so look at the modification time to ensure
        # this test is actually testing the most recent upload
        date_modified = datetime.fromisoformat(test_asset_metadata["dateModified"])
        assert datetime.now() - date_modified < timedelta(minutes=10)
