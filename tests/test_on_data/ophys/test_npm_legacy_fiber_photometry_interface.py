from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import NPMLegacyFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file

from ..setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "sampleData_NPM_5"
FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "npm_legacy_fiber_photometry_metadata.yaml"

# Values demultiplexed from PagCeAVgatFear_1512_1.csv, a header-less legacy file: column 0 is the
# timestamp (milliseconds) and columns 1-3 are three region/data columns. With number_of_channels=2
# the rows cycle chev (even rows) / chod (odd rows), so each of the three data columns yields a
# chev{j} and a chod{j} stream. The per-channel rate and second timestamp follow from the chev-row
# timestamp spacing ((40263564.2624 - 40263510.4768) / 1000 = 0.0537856 s).
EXPECTED_STREAM_NAMES = ["file0_chev1", "file0_chev2", "file0_chev3", "file0_chod1", "file0_chod2", "file0_chod3"]
EXPECTED_RATE = 19.931322423893146
EXPECTED_SAMPLES_PER_CHANNEL = 14773
EXPECTED_SECOND_TIMESTAMP = 0.053785599999129775
# First sample of each stream (data columns 1/2/3 of the channel's first row).
EXPECTED_FIRST_VALUES = {
    "file0_chev1": 6558.51912568306,
    "file0_chev2": 4429.46076529713,
    "file0_chev3": 7018.70428495856,
    "file0_chod1": 4822.62295081967,
    "file0_chod2": 3898.81713983424,
    "file0_chod3": 6989.94886263446,
}


class TestNPMLegacyFiberPhotometryInterface:
    @pytest.fixture
    def interface(self):
        return NPMLegacyFiberPhotometryInterface(
            folder_path=NPM_FOLDER, number_of_channels=2, time_unit="milliseconds", verbose=False
        )

    @pytest.fixture
    def metadata(self, interface):
        editable_metadata = load_dict_from_file(FIBER_PHOTOMETRY_METADATA_FILE)
        return dict_deep_update(interface.get_metadata(), editable_metadata)

    def test_construction(self, interface):
        assert interface.source_data["folder_path"] == NPM_FOLDER

    def test_too_many_channels_raises(self):
        with pytest.raises(ValueError, match="1-3"):
            NPMLegacyFiberPhotometryInterface(folder_path=NPM_FOLDER, number_of_channels=4, time_unit="milliseconds")

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        """NPM recordings carry no embedded start time, so the interface must not invent one."""
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_stream_discovery_demultiplexes_channels(self, interface):
        """The header-less interleaved CSV row-cycles into chev (even rows) and chod (odd rows)
        channels for each of the three data columns; the 2-column event CSV is excluded."""
        assert sorted(interface._get_stream_names()) == EXPECTED_STREAM_NAMES

    def test_demultiplexed_values(self, interface):
        """Each channel keeps every other row, normalized to start at zero, with millisecond
        timestamps scaled to seconds."""
        for stream_name, expected_first_value in EXPECTED_FIRST_VALUES.items():
            stream = interface._read_stream(stream_name)
            assert stream["data"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
            assert stream["timestamps"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
            np.testing.assert_allclose(stream["data"][0], expected_first_value, rtol=1e-9)
            np.testing.assert_allclose(stream["timestamps"][0], 0.0, atol=1e-12)
            np.testing.assert_allclose(stream["timestamps"][1], EXPECTED_SECOND_TIMESTAMP, rtol=1e-9)
            np.testing.assert_allclose(stream["rate"], EXPECTED_RATE, rtol=1e-9)

    def test_get_original_starting_time_and_rate(self, interface):
        starting_time_and_rate = interface.get_original_starting_time_and_rate()
        assert set(starting_time_and_rate) == set(EXPECTED_STREAM_NAMES)
        for starting_time, rate in starting_time_and_rate.values():
            assert starting_time == 0.0
            np.testing.assert_allclose(rate, EXPECTED_RATE, rtol=1e-9)

    def test_set_aligned_starting_time(self, interface):
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        timestamps = interface.get_timestamps()
        for stream_name in EXPECTED_STREAM_NAMES:
            assert timestamps[stream_name][0] == 10.0

    def test_run_conversion_writes_response_series(self, interface, metadata, tmp_path):
        nwbfile_path = tmp_path / "npm_legacy_fiber_photometry.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            response_series_names = {
                name
                for name, obj in nwbfile.acquisition.items()
                if obj.neurodata_type == "FiberPhotometryResponseSeries"
            }
            assert response_series_names == {
                "calcium_signal_region0",
                "isosbestic_control_region0",
                "calcium_signal_region1",
                "isosbestic_control_region1",
                "calcium_signal_region2",
                "isosbestic_control_region2",
            }

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert len(fiber_photometry_table) == 6

            signal_series = nwbfile.acquisition["calcium_signal_region0"]
            control_series = nwbfile.acquisition["isosbestic_control_region0"]
            # stub_test reads ~1 second (ceil(rate)) of samples.
            assert signal_series.data.shape[0] == int(np.ceil(EXPECTED_RATE))
            np.testing.assert_allclose(signal_series.data[0], EXPECTED_FIRST_VALUES["file0_chod1"], rtol=1e-9)
            np.testing.assert_allclose(control_series.data[0], EXPECTED_FIRST_VALUES["file0_chev1"], rtol=1e-9)
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-9)
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]
            assert list(control_series.fiber_photometry_table_region.data[:]) == [1]

    def test_run_conversion_aligned_timestamps(self, interface, metadata, tmp_path):
        original_timestamps = interface.get_original_timestamps()
        shifted_timestamps = {name: timestamps + 7.0 for name, timestamps in original_timestamps.items()}
        interface.set_aligned_timestamps(shifted_timestamps)
        nwbfile_path = tmp_path / "npm_legacy_fiber_photometry_timestamps.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            timing_source="aligned_timestamps",
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal_region0"]
            assert signal_series.timestamps[0] == 7.0
            assert signal_series.timestamps.shape[0] == signal_series.data.shape[0]
