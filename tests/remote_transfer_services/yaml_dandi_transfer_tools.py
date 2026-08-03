import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dandi.dandiapi
import pytest
from dandi.exceptions import NotFoundError

from neuroconv import run_conversion_from_yaml

from ..test_on_data.setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

DANDI_SANDBOX_API_KEY = os.getenv("DANDI_SANDBOX_API_KEY")
HAVE_DANDI_KEY = DANDI_SANDBOX_API_KEY is not None and DANDI_SANDBOX_API_KEY != ""  # can be "" from external forks

MAXIMUM_WAIT_IN_SECONDS = 120
POLL_INTERVAL_IN_SECONDS = 2


def _asset_is_from_this_run(dandiset: dandi.dandiapi.RemoteDandiset, asset_path: str) -> bool:
    """Whether the sandbox holds an asset at this path that this run uploaded.

    Past runs leave an asset at the same path, so existence alone is not enough: the modification time is
    what separates the upload under test from its predecessor.
    """
    try:
        asset = dandiset.get_asset_by_path(path=asset_path)
    except NotFoundError:
        return False

    date_modified = datetime.fromisoformat(asset.get_raw_metadata()["dateModified"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - date_modified < timedelta(minutes=10)


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_SANDBOX_API_KEY to run this test!",
)
def test_run_conversion_from_yaml_with_dandi_upload():
    path_to_test_yml_files = Path(__file__).parent.parent / "test_on_data" / "test_yaml" / "conversion_specifications"
    yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_dandi_upload.yml"
    run_conversion_from_yaml(
        specification_file_path=yaml_file_path,
        data_folder_path=ECEPHY_DATA_PATH,
        output_folder_path=OUTPUT_PATH,
        overwrite=True,
    )

    client = dandi.dandiapi.DandiAPIClient(api_url="https://api.sandbox.dandiarchive.org/api")
    dandiset = client.get_dandiset("200560")

    expected_asset_paths = [
        "sub-yaml-1/sub-yaml-1_ses-test-yaml-1_ecephys.nwb",
        "sub-yaml-002/sub-yaml-002_ses-test-yaml-2_ecephys.nwb",
        "sub-YAML-Subject-Name/sub-YAML-Subject-Name_ses-test-YAML-3_ecephys.nwb",
    ]

    # The sandbox needs a moment to register an upload, so wait for it rather than sleeping a flat minute:
    # this returns as soon as the server is ready and still fails if it never becomes ready.
    deadline = time.monotonic() + MAXIMUM_WAIT_IN_SECONDS
    while True:
        pending_asset_paths = [path for path in expected_asset_paths if not _asset_is_from_this_run(dandiset, path)]
        if not pending_asset_paths:
            break
        assert time.monotonic() < deadline, (
            f"The DANDI sandbox did not report {pending_asset_paths} as uploaded by this run "
            f"within {MAXIMUM_WAIT_IN_SECONDS} seconds!"
        )
        time.sleep(POLL_INTERVAL_IN_SECONDS)
