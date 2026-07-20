"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import re
from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_array_equal

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
        # The mock contributes only a session start time: location, wavelengths and the indicator label
        # describe a preparation a synthetic source does not have, so they are left to the user. What is
        # present here is the base's own scaffold, still holding its placeholder sentinels (see #1789).
        interface = MockFiberPhotometryInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        metadata = interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 1, 1, tzinfo=timezone.utc)

        rows = metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]
        assert all(row["location"] == "PLACEHOLDER" for row in rows.values())
        assert metadata["FiberPhotometry"]["FiberPhotometryIndicators"]["indicator"]["label"] == "PLACEHOLDER"

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

    def test_table_comes_from_user_metadata(self):
        # The complement of the above: supplying a table row per stream is the user's job, and doing so
        # produces a coherent file (two channels described by two fibers).
        interface = MockFiberPhotometryInterface()
        metadata = interface.get_metadata()
        table_metadata = metadata["FiberPhotometry"]["FiberPhotometryTable"]
        table_metadata["description"] = "Two fibers."
        table_metadata["rows"] = {
            f"row{index}": dict(
                location="prefrontal cortex",
                excitation_wavelength_in_nm=excitation_wavelength_in_nm,
                emission_wavelength_in_nm=525.0,
                indicator_metadata_key="indicator",
                optical_fiber_metadata_key="optical_fiber",
                excitation_source_metadata_key="excitation_source",
                photodetector_metadata_key="photodetector",
            )
            for index, excitation_wavelength_in_nm in enumerate([465.0, 405.0])
        }
        metadata["FiberPhotometry"]["FiberPhotometryIndicators"]["indicator"]["label"] = "GCaMP"
        metadata["FiberPhotometry"][interface.metadata_key]["fiber_photometry_table_region"] = ["row0", "row1"]

        nwbfile = interface.create_nwbfile(metadata=metadata)

        table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
        assert len(table) == 2
        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100, 2)
