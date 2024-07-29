from datetime import datetime
from pathlib import Path

from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    TDTFiberPhotometryInterfaceMixin,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file

try:
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OUTPUT_PATH


class TestTDTFiberPhotometryInterface(TestCase, TDTFiberPhotometryInterfaceMixin):
    data_interface_cls = TDTFiberPhotometryInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "fiber_photometry_datasets" / "Photo_249_391-200721-120136"),
    )
    save_directory = OUTPUT_PATH
    expected_session_start_time = datetime(2020, 7, 21, 10, 2, 24, 999999).isoformat()

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # for event_dict in self.expected_events:
            #     expected_name = event_dict["name"]
            #     expected_description = event_dict["description"]
            #     assert expected_name in nwbfile.processing["behavior"].data_interfaces
            #     event = nwbfile.processing["behavior"].data_interfaces[expected_name]
            #     assert event.description == expected_description

            # for interval_dict in self.expected_interval_series:
            #     expected_name = interval_dict["name"]
            #     expected_description = interval_dict["description"]
            #     assert expected_name in nwbfile.processing["behavior"]["behavioral_epochs"].interval_series
            #     interval_series = nwbfile.processing["behavior"]["behavioral_epochs"].interval_series[expected_name]
            #     assert interval_series.description == expected_description

    def test_all_conversion_checks(self):
        metadata_file_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        editable_metadata = load_dict_from_file(metadata_file_path)
        metadata = self.data_interface_cls(**self.interface_kwargs).get_metadata()
        metadata = dict_deep_update(metadata, editable_metadata)

        super().test_all_conversion_checks(metadata=metadata)
