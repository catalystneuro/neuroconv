import numpy as np
from pynwb import read_nwb

from neuroconv.datainterfaces import AxonaPositionDataInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

AXONA_PATH = ECEPHY_DATA_PATH / "axona"


class TestAxonaPositionPosFile(DataInterfaceTestMixin):
    data_interface_cls = AxonaPositionDataInterface
    interface_kwargs = dict(file_path=str(AXONA_PATH / "dataset_unit_spikes" / "20140815-180secs.pos"))

    expected_number_of_samples = 9000
    expected_last_timestamp = 180.0

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["Position"]
        for spatial_series in position.spatial_series.values():
            timestamps = spatial_series.timestamps[:]
            assert len(timestamps) == self.expected_number_of_samples
            assert timestamps[0] == 0.0
            np.testing.assert_allclose(timestamps[-1], self.expected_last_timestamp)
        nwbfile.read_io.close()


class TestAxonaPositionMultiModalPosFile(DataInterfaceTestMixin):
    data_interface_cls = AxonaPositionDataInterface
    interface_kwargs = dict(file_path=str(AXONA_PATH / "dataset_multi_modal" / "axona_sample.pos"))

    expected_number_of_samples = 100
    expected_last_timestamp = 1.2

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["Position"]
        for spatial_series in position.spatial_series.values():
            timestamps = spatial_series.timestamps[:]
            assert len(timestamps) == self.expected_number_of_samples
            assert timestamps[0] == 0.0
            np.testing.assert_allclose(timestamps[-1], self.expected_last_timestamp)
        nwbfile.read_io.close()


class TestAxonaPositionBinFile(DataInterfaceTestMixin):
    data_interface_cls = AxonaPositionDataInterface
    interface_kwargs = dict(file_path=str(AXONA_PATH / "dataset_multi_modal" / "axona_sample.bin"))

    expected_number_of_samples = 61
    expected_last_timestamp = 1.186

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        position = nwbfile.processing["behavior"]["Position"]
        for spatial_series in position.spatial_series.values():
            timestamps = spatial_series.timestamps[:]
            assert len(timestamps) == self.expected_number_of_samples
            assert timestamps[0] == 0.0
            np.testing.assert_allclose(timestamps[-1], self.expected_last_timestamp)
        nwbfile.read_io.close()
