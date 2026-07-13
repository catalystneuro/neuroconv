from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from neuroconv.datainterfaces import CSVFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

# Parameters for the dynamically generated CSVs. All values are dyadic (SAMPLING_RATE is a power of
# two, data values are multiples of 1/4), so the CSV text round-trips losslessly and the written
# arrays compare exactly-equal on every platform.
SAMPLING_RATE = 128.0
NUM_SAMPLES = 20
STUB_SAMPLES = 5
TIMESTAMPS = np.arange(NUM_SAMPLES) / SAMPLING_RATE  # k / 128
SIGNAL_DATA = 0.5 * np.arange(NUM_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ...
CONTROL_DATA = 0.25 * np.arange(NUM_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ...


class TestCSVFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """Single-series CSV fiber photometry interface (one FiberPhotometryResponseSeries)."""

    data_interface_cls = CSVFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # First STUB_SAMPLES samples of the "data" column, written from the bare scaffold metadata.
    expected_response_series_data = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    # Regular timestamps (k / 128), so the series is written as starting_time + rate.
    expected_starting_time = 0.0
    expected_rate = SAMPLING_RATE

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):
        cls = request.cls
        data_directory = tmp_path_factory.mktemp("csv_fiber_photometry")
        signal_path = data_directory / "Sample_Signal_Channel.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        cls.signal_path = signal_path
        cls.interface_kwargs = dict(
            file_path=signal_path,
            data_columns="data",
            timestamps_column="timestamps",
            metadata_key="calcium_signal",
        )

    def check_extracted_metadata(self, metadata: dict):
        # CSV recordings carry no embedded start time, so the interface must not invent one.
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_default_metadata_warns_about_placeholders(self, setup_interface):
        # CSV has no embedded session_start_time (see check_extracted_metadata), so unlike the base
        # mixin's version we must supply one before the file can be built; the placeholder warning for
        # the still-unset fiber photometry fields must then still fire.
        metadata = self.interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        with pytest.warns(UserWarning, match="placeholder"):
            self.interface.create_nwbfile(metadata=metadata, stub_test=True)

    def test_get_available_columns(self):
        assert CSVFiberPhotometryInterface.get_available_columns(file_path=self.signal_path) == ["timestamps", "data"]

    def test_metadata_key_generated_from_data_columns(self):
        """With no explicit metadata_key, it is derived from data_columns."""
        interface = CSVFiberPhotometryInterface(
            file_path=self.signal_path, data_columns="data", timestamps_column="timestamps"
        )
        assert interface.metadata_key == "fiber_photometry_data"
        assert interface.metadata_key in interface.get_metadata()["FiberPhotometry"]

    def test_read_header_less_csv_by_integer_position(self, tmp_path):
        """Integer column identifiers address a header-less CSV by position."""
        path = tmp_path / "header_less.csv"
        pd.DataFrame({"a": TIMESTAMPS, "b": SIGNAL_DATA}).to_csv(path, index=False, header=False)
        interface = CSVFiberPhotometryInterface(file_path=path, data_columns=1, timestamps_column=0)
        np.testing.assert_array_equal(interface.get_original_timestamps(), TIMESTAMPS)
        np.testing.assert_array_equal(interface._get_stream_data(stream_name=1), SIGNAL_DATA)

    def test_multiple_data_columns_stack_into_multichannel_series(self, tmp_path):
        """A list of data_columns is column-stacked into one multi-channel response series."""
        path = tmp_path / "wide.csv"
        pd.DataFrame({"time": TIMESTAMPS, "signal": SIGNAL_DATA, "control": CONTROL_DATA}).to_csv(path, index=False)
        interface = CSVFiberPhotometryInterface(
            file_path=path, data_columns=["signal", "control"], timestamps_column="time"
        )
        data = interface._read_response_data()
        assert data.shape == (NUM_SAMPLES, 2)
        np.testing.assert_array_equal(data[:, 0], SIGNAL_DATA)
        np.testing.assert_array_equal(data[:, 1], CONTROL_DATA)
