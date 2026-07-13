from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from neuroconv.datainterfaces import CSVFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

# Parameters for the dynamically generated stream CSVs. All values are dyadic (SAMPLING_RATE is a
# power of two, data values are multiples of 1/4), so the CSV text round-trips losslessly and the
# written arrays compare exactly-equal on every platform.
SAMPLING_RATE = 128.0
NUM_SAMPLES = 20
STUB_SAMPLES = 5
TIMESTAMPS = np.arange(NUM_SAMPLES) / SAMPLING_RATE  # k / 128
SIGNAL_DATA = 0.5 * np.arange(NUM_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ...
CONTROL_DATA = 0.25 * np.arange(NUM_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ...


def _write_stream_csv(path, data):
    """Write one data stream CSV with ``timestamps`` and ``data`` columns."""
    pd.DataFrame({"timestamps": TIMESTAMPS, "data": data}).to_csv(path, index=False)


class TestCSVFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """Single-series CSV fiber photometry interface (one FiberPhotometryResponseSeries)."""

    data_interface_cls = CSVFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # First STUB_SAMPLES samples of Sample_Signal_Channel, written from the bare scaffold metadata.
    expected_response_series_data = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    # Regular timestamps (k / 128), so the series is written as starting_time + rate.
    expected_starting_time = 0.0
    expected_rate = SAMPLING_RATE

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):
        cls = request.cls
        folder_path = tmp_path_factory.mktemp("csv_fiber_photometry")
        _write_stream_csv(folder_path / "Sample_Signal_Channel.csv", SIGNAL_DATA)
        _write_stream_csv(folder_path / "Sample_Control_Channel.csv", CONTROL_DATA)
        # A single-column event CSV to verify stream discovery excludes it.
        (folder_path / "Sample_TTL.csv").write_text("timestamps\n1.0\n2.0\n")
        cls.folder_path = folder_path
        cls.interface_kwargs = dict(
            folder_path=folder_path, stream_names="Sample_Signal_Channel", metadata_key="calcium_signal"
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

    def test_get_available_streams_excludes_event_csv(self):
        """Only the data CSVs are streams; the single-column TTL CSV is excluded."""
        assert CSVFiberPhotometryInterface.get_available_streams(folder_path=self.folder_path) == [
            "Sample_Control_Channel",
            "Sample_Signal_Channel",
        ]

    def test_metadata_key_generated_from_stream_names(self):
        """With no explicit metadata_key, it is derived from stream_names."""
        interface = CSVFiberPhotometryInterface(folder_path=self.folder_path, stream_names="Sample_Signal_Channel")
        assert interface.metadata_key == "fiber_photometry_sample_signal_channel"
        assert interface.metadata_key in interface.get_metadata()["FiberPhotometry"]
