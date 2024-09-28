import os
import platform
import time
from datetime import datetime, timedelta
from pathlib import Path

import dandi.dandiapi
import pytest
from packaging.version import Version

from neuroconv import run_conversion_from_yaml

from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

DANDI_API_KEY = os.getenv("DANDI_API_KEY")
HAVE_DANDI_KEY = DANDI_API_KEY is not None and DANDI_API_KEY != ""  # can be "" from external forks
_PYTHON_VERSION = platform.python_version()


@pytest.mark.skipif(
    not HAVE_DANDI_KEY or Version(".".join(_PYTHON_VERSION.split(".")[:2])) != Version("3.12"),
    reason="You must set your DANDI_API_KEY to run this test!",
)
def test_run_conversion_from_yaml_with_dandi_upload():
    path_to_test_yml_files = Path(__file__).parent / "conversion_specifications"
    yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_dandi_upload.yml"
    run_conversion_from_yaml(
        specification_file_path=yaml_file_path,
        data_folder_path=ECEPHY_DATA_PATH,
        output_folder_path=OUTPUT_PATH,
        overwrite=True,
    )

    time.sleep(60)  # Give some buffer room for server to process before making assertions against DANDI API

    client = dandi.dandiapi.DandiAPIClient(api_url="https://api-staging.dandiarchive.org/api")
    dandiset = client.get_dandiset("200560")

    expected_asset_paths = [
        "sub-yaml-1/sub-yaml-1_ses-test-yaml-1_ecephys.nwb",
        "sub-yaml-002/sub-yaml-002_ses-test-yaml-2_ecephys.nwb",
        "sub-YAML-Subject-Name/sub-YAML-Subject-Name_ses-test-YAML-3_ecephys.nwb",
    ]
    for asset_path in expected_asset_paths:
        test_asset = dandiset.get_asset_by_path(path=asset_path)  # Will error if not found
        test_asset_metadata = test_asset.get_raw_metadata()

        # Past uploads may have created the same apparent file, so look at the modification time to ensure
        # this test is actually testing the most recent upload
        date_modified = datetime.fromisoformat(
            test_asset_metadata["dateModified"].split("Z")[0]  # Timezones look a little messy
        )
        assert datetime.now() - date_modified < timedelta(minutes=10)
