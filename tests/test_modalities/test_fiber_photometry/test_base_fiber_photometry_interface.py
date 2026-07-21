"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import re
from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface


class TestMockFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    data_interface_cls = MockFiberPhotometryInterface
    interface_kwargs = dict()
    conversion_options = dict(stub_test=True, stub_samples=3)

    # Hand-supplied, not read back from the interface: the mock's two seeded standard-normal traces.
    expected_response_series_data = np.array(
        [
            [0.1257302210933933, 0.345584192064786],
            [-0.1321048632913019, 0.8216181435011584],
            [0.6404226504432821, 0.33043707618338714],
        ]
    )
    expected_rate = 100.0
    expected_starting_time = 0.0

    def test_get_metadata_adds_no_provenance(self):
        # A synthetic source has no optical hardware, indicator, or table to describe, so the default
        # metadata fabricates none of it (see #1789) — only the response-series entry and the mock's
        # session start time. The full chain is opt-in via get_example_metadata.
        interface = MockFiberPhotometryInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        metadata = interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 1, 1, tzinfo=timezone.utc)

        fiber_photometry_metadata = metadata["FiberPhotometry"]
        assert "FiberPhotometryTable" not in fiber_photometry_metadata
        assert "FiberPhotometryIndicators" not in fiber_photometry_metadata
        assert not metadata.get("Devices")
        assert not metadata.get("DeviceModels")

        # The series entry carries only a default name — no fabricated description, and no unit (unit is a
        # property of the data, supplied when the series is built, not editable metadata).
        series_metadata = fiber_photometry_metadata[interface.metadata_key]
        assert series_metadata["name"] == "FiberPhotometryResponseSeries"
        assert "unit" not in series_metadata
        assert "description" not in series_metadata

    def test_metadata_key_override(self):
        # An explicit metadata_key names the response-series entry instead of the stream-derived default.
        interface = MockFiberPhotometryInterface(metadata_key="my_series")
        assert interface.metadata_key == "my_series"
        assert "my_series" in interface.get_metadata()["FiberPhotometry"]

    def test_channel_order_follows_stream_names(self):
        # Which channel a stream lands on is positional: np.concatenate(axis=1) preserves stream_names
        # order, and nothing downstream re-derives it, so the table region has to line up by position.
        interface = MockFiberPhotometryInterface(stream_names=["first", "second", "third"])
        data = interface._read_response_data()

        assert data.shape == (100, 3)
        for index, stream_name in enumerate(interface.stream_names):
            assert_array_equal(data[:, index], interface._get_stream_data(stream_name=stream_name))

    def test_multi_channel_stream_contributes_one_column_per_channel(self):
        # A single stream can itself be multi-channel (one acquisition store holding several fibers),
        # in which case _get_stream_data returns 2-D and skips the np.newaxis promotion entirely.
        interface = MockFiberPhotometryInterface(stream_names="fibers", channels_per_stream=4)
        stream_data = interface._get_stream_data(stream_name="fibers")
        assert stream_data.ndim == 2

        data = interface._read_response_data()
        assert data.shape == (100, 4)
        assert_array_equal(data, stream_data)

    def test_mixed_channel_counts_stack_by_total_channels(self):
        # The realistic multi-fiber layout: a 3-fiber store at one wavelength plus a 1-channel
        # isosbestic control. Columns total the per-stream channel counts, not the stream count, and
        # the promoted 1-D stream stacks alongside the 2-D one.
        interface = MockFiberPhotometryInterface(stream_names=["signal", "control"], channels_per_stream=[3, 1])
        data = interface._read_response_data()

        assert data.shape == (100, 4)
        assert_array_equal(data[:, :3], interface._get_stream_data(stream_name="signal"))
        assert_array_equal(data[:, 3], interface._get_stream_data(stream_name="control"))

    def test_channels_per_stream_length_mismatch_errors(self):
        expected_error = "channels_per_stream has 3 entries but there are 2 stream(s)"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            MockFiberPhotometryInterface(stream_names=["a", "b"], channels_per_stream=[1, 2, 3])

    def test_single_stream_collapses_to_one_channel(self):
        # A lone column is written as a 1-D series rather than an (N, 1) one.
        interface = MockFiberPhotometryInterface(stream_names="signal")
        nwbfile = interface.create_nwbfile()

        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100,)

    def test_fully_annotated_metadata_round_trips(self, tmp_path):
        # The fully annotated path: get_example_metadata supplies the complete provenance chain, and every
        # piece of it must survive a write/read cycle — device models, devices (with model links and fiber
        # insertion), the indicator, both table rows in full, the region, and the response series.
        interface = MockFiberPhotometryInterface()
        metadata = interface.get_example_metadata()

        nwbfile_path = tmp_path / "fully_annotated.nwb"
        nwbfile = interface.create_nwbfile(metadata=metadata)
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()

            assert read_nwbfile.session_start_time == datetime(2020, 1, 1, tzinfo=timezone.utc)

            # Device models.
            optical_fiber_model = read_nwbfile.device_models["optical_fiber_model"]
            assert optical_fiber_model.manufacturer == "Doric Lenses"
            assert optical_fiber_model.numerical_aperture == 0.48
            excitation_source_model = read_nwbfile.device_models["excitation_source_model"]
            assert excitation_source_model.source_type == "LED"
            assert excitation_source_model.excitation_mode == "one-photon"
            assert read_nwbfile.device_models["photodetector_model"].detector_type == "photodiode"

            # Devices, their model links, and the optical fiber's insertion.
            assert set(read_nwbfile.devices) == {
                "optical_fiber",
                "excitation_source_calcium_signal",
                "excitation_source_isosbestic_control",
                "photodetector",
            }
            optical_fiber = read_nwbfile.devices["optical_fiber"]
            assert optical_fiber.model.name == "optical_fiber_model"
            assert optical_fiber.fiber_insertion.depth_in_mm == 4.0
            assert optical_fiber.fiber_insertion.insertion_position_ap_in_mm == 3.0
            assert read_nwbfile.devices["excitation_source_calcium_signal"].model.name == "excitation_source_model"
            assert read_nwbfile.devices["photodetector"].model.name == "photodetector_model"

            fiber_photometry = read_nwbfile.lab_meta_data["fiber_photometry"]

            # Indicator.
            indicators = fiber_photometry.fiber_photometry_indicators.indicators
            assert indicators["indicator"].label == "GCaMP6s"

            # Table: both rows in full, including the per-row device and indicator references.
            table = fiber_photometry.fiber_photometry_table
            assert len(table) == 2
            assert list(table["location"][:]) == ["VTA", "VTA"]
            assert_array_equal(table["excitation_wavelength_in_nm"][:], np.array([470.0, 405.0]))
            assert_array_equal(table["emission_wavelength_in_nm"][:], np.array([525.0, 525.0]))
            assert table["optical_fiber"][0].name == "optical_fiber"
            assert table["excitation_source"][0].name == "excitation_source_calcium_signal"
            assert table["excitation_source"][1].name == "excitation_source_isosbestic_control"
            assert table["photodetector"][0].name == "photodetector"
            assert table["indicator"][0].label == "GCaMP6s"

            # Response series, referencing both the calcium-signal (row 0) and isosbestic-control (row 1) rows.
            response_series = read_nwbfile.acquisition["FiberPhotometryResponseSeries"]
            assert response_series.name == "FiberPhotometryResponseSeries"
            assert (
                response_series.description
                == "Multi-fiber photometry recording of GCaMP6s calcium signal and isosbestic control."
            )
            assert response_series.unit == "a.u."
            assert response_series.data[:].shape == (100, 2)
            assert response_series.rate == pytest.approx(100.0)
            assert response_series.starting_time == 0.0
            assert list(response_series.fiber_photometry_table_region.data[:]) == [0, 1]

    def test_minimally_annotated_metadata_round_trips(self, tmp_path):
        # The minimally annotated path: the default metadata describes only the response series, so the file
        # must contain exactly that and nothing fabricated — no table region, no devices, no lab metadata.
        interface = MockFiberPhotometryInterface()
        metadata = interface.get_metadata()

        nwbfile_path = tmp_path / "minimally_annotated.nwb"
        nwbfile = interface.create_nwbfile(metadata=metadata)
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()

            response_series = read_nwbfile.acquisition["FiberPhotometryResponseSeries"]
            assert response_series.name == "FiberPhotometryResponseSeries"
            # Nothing fabricated: no description was supplied, so it is written empty.
            assert response_series.description == ""
            assert response_series.unit == "a.u."
            assert response_series.data[:].shape == (100, 2)
            assert response_series.rate == pytest.approx(100.0)
            assert response_series.starting_time == 0.0

            assert response_series.fiber_photometry_table_region is None
            assert len(read_nwbfile.devices) == 0
            assert len(read_nwbfile.device_models) == 0
            assert "fiber_photometry" not in read_nwbfile.lab_meta_data
