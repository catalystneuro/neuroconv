from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import CSVFiberPhotometryInterface
from neuroconv.utils import dict_deep_update

# Parameters for the dynamically generated stream CSVs. NUM_SAMPLES exceeds the default stub_samples
# so that stub_test genuinely truncates the trace. All values are dyadic (SAMPLING_RATE is a power of
# two, data values are multiples of 1/4), so the CSV text round-trips losslessly and the written
# arrays compare exactly-equal on every platform.
SAMPLING_RATE = 128.0
NUM_SAMPLES = 200
STUB_SAMPLES = 50
TIMESTAMPS = np.arange(NUM_SAMPLES) / SAMPLING_RATE  # k / 128
SIGNAL_DATA = 0.5 * np.arange(NUM_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ...
CONTROL_DATA = 0.25 * np.arange(NUM_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ...
SESSION_START_TIME = datetime(2020, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def _write_stream_csv(path, data):
    """Write one data stream CSV with ``timestamps`` and ``data`` columns."""
    pd.DataFrame({"timestamps": TIMESTAMPS, "data": data}).to_csv(path, index=False)


def _fill_placeholder_metadata(metadata, metadata_key):
    """Deep-update the scaffold with the handful of fields the base warns about (plus a start time)."""
    return dict_deep_update(
        metadata,
        {
            "NWBFile": {"session_start_time": SESSION_START_TIME},
            "FiberPhotometry": {
                "FiberPhotometryIndicators": {"indicator": {"label": "GCaMP7b"}},
                "FiberPhotometryTable": {
                    "description": "Fiber photometry system metadata table for the CSV recording.",
                    "rows": {
                        "row0": {
                            "location": "region",
                            "excitation_wavelength_in_nm": 465.0,
                            "emission_wavelength_in_nm": 525.0,
                        }
                    },
                },
                metadata_key: {
                    "name": "calcium_signal",
                    "description": "The fluorescence from the calcium-dependent signal channel.",
                    "fiber_photometry_table_region_description": (
                        "The region of the FiberPhotometryTable corresponding to the calcium signal."
                    ),
                },
            },
        },
    )


class TestCSVFiberPhotometryInterface:
    @pytest.fixture
    def csv_folder(self, tmp_path):
        _write_stream_csv(tmp_path / "Sample_Signal_Channel.csv", SIGNAL_DATA)
        _write_stream_csv(tmp_path / "Sample_Control_Channel.csv", CONTROL_DATA)
        # A single-column event CSV to verify stream discovery excludes it.
        (tmp_path / "Sample_TTL.csv").write_text("timestamps\n1.0\n2.0\n")
        return tmp_path

    @pytest.fixture
    def interface(self, csv_folder):
        return CSVFiberPhotometryInterface(
            folder_path=csv_folder, stream_names="Sample_Signal_Channel", metadata_key="calcium_signal"
        )

    @pytest.fixture
    def metadata(self, interface):
        return _fill_placeholder_metadata(interface.get_metadata(), metadata_key="calcium_signal")

    def test_construction(self, interface, csv_folder):
        assert interface.source_data["folder_path"] == csv_folder
        assert interface.stream_names == ["Sample_Signal_Channel"]
        assert interface.metadata_key == "calcium_signal"

    def test_get_available_streams_excludes_event_csv(self, csv_folder):
        """Only the data CSVs are streams; the single-column TTL CSV is excluded."""
        assert CSVFiberPhotometryInterface.get_available_streams(folder_path=csv_folder) == [
            "Sample_Control_Channel",
            "Sample_Signal_Channel",
        ]

    def test_metadata_key_generated_from_stream_names(self, csv_folder):
        """With no explicit metadata_key, it is derived from stream_names."""
        interface = CSVFiberPhotometryInterface(folder_path=csv_folder, stream_names="Sample_Signal_Channel")
        assert interface.metadata_key == "fiber_photometry_sample_signal_channel"
        assert interface.metadata_key in interface.get_metadata()["FiberPhotometry"]

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        """CSV recordings carry no embedded start time, so the interface must not invent one."""
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_get_original_timestamps(self, interface):
        np.testing.assert_array_equal(interface.get_original_timestamps(), TIMESTAMPS)

    def test_set_aligned_timestamps(self, interface):
        shifted = TIMESTAMPS + 10.0
        interface.set_aligned_timestamps(shifted)
        np.testing.assert_array_equal(interface.get_timestamps(), shifted)

    def test_run_on_zero_user_metadata(self, interface, tmp_path):
        """The scaffold is complete: conversion runs with no user metadata (only a start time), warning
        about the surviving placeholder sentinels."""
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = SESSION_START_TIME
        nwbfile_path = tmp_path / "csv_fiber_photometry_scaffold.nwb"
        with pytest.warns(UserWarning, match="placeholder"):
            interface.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True, stub_test=True)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert "FiberPhotometryResponseSeries" in nwbfile.acquisition

    def test_run_conversion_writes_response_series(self, interface, metadata, tmp_path):
        """With stub_test=False the entire trace is written as a regularly-sampled series."""
        nwbfile_path = tmp_path / "csv_fiber_photometry.nwb"
        interface.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True, stub_test=False)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            assert set(nwbfile.acquisition) == {"calcium_signal"}
            signal_series = nwbfile.acquisition["calcium_signal"]
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA)
            assert signal_series.rate == SAMPLING_RATE
            assert signal_series.starting_time == 0.0

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert len(fiber_photometry_table) == 1
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]

    def test_run_conversion_stub_test_truncates_trace(self, interface, metadata, tmp_path):
        """With stub_test=True only the first stub_samples samples are written."""
        nwbfile_path = tmp_path / "csv_fiber_photometry_stub.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            stub_samples=STUB_SAMPLES,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal"]
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA[:STUB_SAMPLES])
            assert signal_series.rate == SAMPLING_RATE

    def test_run_conversion_always_write_timestamps(self, interface, metadata, tmp_path):
        """always_write_timestamps writes an explicit timestamps array even for a regular series."""
        nwbfile_path = tmp_path / "csv_fiber_photometry_timestamps.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            stub_samples=STUB_SAMPLES,
            always_write_timestamps=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal"]
            np.testing.assert_array_equal(signal_series.timestamps[:], TIMESTAMPS[:STUB_SAMPLES])
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA[:STUB_SAMPLES])

    def test_strict_raises_on_placeholder_metadata(self, interface, tmp_path):
        """strict=True turns the placeholder warning into an error."""
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = SESSION_START_TIME
        nwbfile_path = tmp_path / "csv_fiber_photometry_strict.nwb"
        with pytest.raises(ValueError, match="placeholder"):
            interface.run_conversion(
                nwbfile_path=str(nwbfile_path),
                metadata=metadata,
                overwrite=True,
                stub_test=True,
                strict=True,
            )
