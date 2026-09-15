import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from platform import python_version as get_python_version

import dandi.dandiapi
import pytest
import yaml
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


def _write_specification_with_platform_token(
    yaml_file_path: Path, platform_token: str, destination_folder: Path
) -> Path:
    """Copy the specification with `platform_token` appended to every subject and session identifier.

    The identifiers in the checked-in specification are fixed, so every leg of every run wrote the same
    three asset paths into one dandiset. Two runs overlapping then replaced each other's assets, and since
    an asset update detaches the record it replaces, whichever run lost the race was left holding
    identifiers the draft version no longer contained.
    """
    with open(file=yaml_file_path, mode="r", encoding="utf-8") as io:
        specification = yaml.safe_load(io)

    for experiment in specification["experiments"].values():
        for session in experiment["sessions"]:
            nwbfile_metadata = session["metadata"]["NWBFile"]
            subject_metadata = session["metadata"]["Subject"]
            nwbfile_metadata["session_id"] = f"{nwbfile_metadata['session_id']}-{platform_token}"
            subject_metadata["subject_id"] = f"{subject_metadata['subject_id']}-{platform_token}"

    destination_path = destination_folder / "GIN_conversion_specification_dandi_upload_with_platform_token.yml"
    with open(file=destination_path, mode="w", encoding="utf-8") as io:
        yaml.safe_dump(specification, io)

    return destination_path


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_SANDBOX_API_KEY to run this test!",
)
def test_run_conversion_from_yaml_with_dandi_upload(tmp_path):
    path_to_test_yml_files = Path(__file__).parent.parent / "test_on_data" / "test_yaml" / "conversion_specifications"
    yaml_file_path = path_to_test_yml_files / "GIN_conversion_specification_dandi_upload.yml"

    # The same namespace the sibling tests use: bounded by the matrix, so each leg overwrites its own
    # three assets instead of leaving new ones in the sandbox on every run.
    platform_token = f"{sys.platform}-{get_python_version().replace('.', '-')}"
    specification_file_path = _write_specification_with_platform_token(
        yaml_file_path=yaml_file_path, platform_token=platform_token, destination_folder=tmp_path
    )

    run_conversion_from_yaml(
        specification_file_path=specification_file_path,
        data_folder_path=ECEPHY_DATA_PATH,
        output_folder_path=OUTPUT_PATH,
        overwrite=True,
    )

    client = dandi.dandiapi.DandiAPIClient(api_url="https://api.sandbox.dandiarchive.org/api")
    dandiset = client.get_dandiset("200560")

    # DANDI turns the spaces of the third session's identifiers into dashes, which is why that path is
    # spelled differently from the specification.
    expected_asset_paths = [
        f"sub-yaml-1-{platform_token}/sub-yaml-1-{platform_token}_ses-test-yaml-1-{platform_token}_ecephys.nwb",
        f"sub-yaml-002-{platform_token}/sub-yaml-002-{platform_token}_ses-test-yaml-2-{platform_token}_ecephys.nwb",
        (
            f"sub-YAML-Subject-Name-{platform_token}/"
            f"sub-YAML-Subject-Name-{platform_token}_ses-test-YAML-3-{platform_token}_ecephys.nwb"
        ),
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
