import shutil

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import AxonaPositionDataInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

AXONA_PATH = ECEPHY_DATA_PATH / "axona"


@pytest.mark.parametrize(
    "relative_file_path, expected_number_of_samples, expected_last_timestamp",
    [
        ("dataset_unit_spikes/20140815-180secs.pos", 9000, 180.0),
        ("dataset_multi_modal/axona_sample.pos", 100, 1.2),
        ("dataset_multi_modal/axona_sample.bin", 61, 1.186),
    ],
)
def test_timestamps_are_written_in_seconds(relative_file_path, expected_number_of_samples, expected_last_timestamp):
    interface = AxonaPositionDataInterface(file_path=str(AXONA_PATH / relative_file_path))
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    position = nwbfile.processing["behavior"]["Position"]
    for spatial_series in position.spatial_series.values():
        assert len(spatial_series.timestamps) == expected_number_of_samples
        assert spatial_series.timestamps[0] == 0.0
        np.testing.assert_allclose(spatial_series.timestamps[-1], expected_last_timestamp)


def test_folder_with_a_dot_in_its_name(tmp_path):
    source_folder = AXONA_PATH / "dataset_unit_spikes"
    folder_with_dot = tmp_path / "session.v1"
    folder_with_dot.mkdir()
    for suffix in (".pos", ".set"):
        shutil.copy(source_folder / f"20140815-180secs{suffix}", folder_with_dot)

    interface = AxonaPositionDataInterface(file_path=str(folder_with_dot / "20140815-180secs.pos"))
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    spatial_series = nwbfile.processing["behavior"]["Position"].spatial_series["X"]
    assert spatial_series.timestamps[-1] == 180.0
