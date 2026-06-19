from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import CSVFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file

from ..setup_paths import OPHYS_DATA_PATH

CSV_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "CSV" / "sample_data_csv_1"
FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "csv_fiber_photometry_metadata.yaml"

# First-row values read directly from the stub CSV heads.
EXPECTED_RATE = 1017.2526245117188
EXPECTED_SIGNAL_FIRST_VALUE = 0.0827529206871986
EXPECTED_CONTROL_FIRST_VALUE = 0.5051592588424683


class TestCSVFiberPhotometryInterface:
    @pytest.fixture
    def interface(self):
        return CSVFiberPhotometryInterface(folder_path=CSV_FOLDER, verbose=False)

    @pytest.fixture
    def metadata(self, interface):
        editable_metadata = load_dict_from_file(FIBER_PHOTOMETRY_METADATA_FILE)
        return dict_deep_update(interface.get_metadata(), editable_metadata)

    def test_construction(self, interface):
        assert interface.source_data["folder_path"] == CSV_FOLDER

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        """CSV recordings carry no embedded start time, so the interface must not invent one."""
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_stream_discovery_excludes_event_csv(self, interface):
        """Only the 3-column data CSVs are streams; the single-column TTL CSV is excluded."""
        assert sorted(interface._get_stream_names()) == ["Sample_Control_Channel", "Sample_Signal_Channel"]

    def test_get_original_starting_time_and_rate(self, interface):
        starting_time_and_rate = interface.get_original_starting_time_and_rate()
        assert starting_time_and_rate == {
            "Sample_Signal_Channel": (0.0, EXPECTED_RATE),
            "Sample_Control_Channel": (0.0, EXPECTED_RATE),
        }

    def test_set_aligned_starting_time(self, interface):
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        timestamps = interface.get_timestamps()
        assert timestamps["Sample_Signal_Channel"][0] == 10.0
        assert timestamps["Sample_Control_Channel"][0] == 10.0

    def test_run_conversion_writes_response_series(self, interface, metadata, tmp_path):
        nwbfile_path = tmp_path / "csv_fiber_photometry.nwb"
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
            assert response_series_names == {"calcium_signal", "isosbestic_control"}

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert len(fiber_photometry_table) == 2

            signal_series = nwbfile.acquisition["calcium_signal"]
            control_series = nwbfile.acquisition["isosbestic_control"]
            # stub_test reads ~1 second (ceil(rate)) of samples.
            assert signal_series.data.shape[0] == int(np.ceil(EXPECTED_RATE))
            np.testing.assert_allclose(signal_series.data[0], EXPECTED_SIGNAL_FIRST_VALUE, rtol=1e-7)
            np.testing.assert_allclose(control_series.data[0], EXPECTED_CONTROL_FIRST_VALUE, rtol=1e-7)
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-7)
            # Each response series links to its own single-row region of the table.
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]
            assert list(control_series.fiber_photometry_table_region.data[:]) == [1]

    def test_run_conversion_aligned_starting_time_and_rate(self, interface, metadata, tmp_path):
        interface.set_aligned_starting_time_and_rate(
            {
                "Sample_Signal_Channel": (5.0, EXPECTED_RATE),
                "Sample_Control_Channel": (5.0, EXPECTED_RATE),
            }
        )
        nwbfile_path = tmp_path / "csv_fiber_photometry_aligned.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            timing_source="aligned_starting_time_and_rate",
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal"]
            assert signal_series.starting_time == 5.0
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-7)

    def test_run_conversion_aligned_timestamps(self, interface, metadata, tmp_path):
        original_timestamps = interface.get_original_timestamps()
        shifted_timestamps = {name: timestamps + 7.0 for name, timestamps in original_timestamps.items()}
        interface.set_aligned_timestamps(shifted_timestamps)
        nwbfile_path = tmp_path / "csv_fiber_photometry_timestamps.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            timing_source="aligned_timestamps",
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal"]
            # First aligned timestamp is the original 0.0 shifted by 7.0; length matches the stub data.
            assert signal_series.timestamps[0] == 7.0
            assert signal_series.timestamps.shape[0] == signal_series.data.shape[0]
