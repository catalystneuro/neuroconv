"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import re

import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface


class TestMockFiberPhotometryInterface:
    def test_get_metadata(self):
        interface = MockFiberPhotometryInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        fiber_photometry_metadata = interface.get_metadata()["FiberPhotometry"]
        # The default two streams give one table row each, with real (non-placeholder) values.
        rows = fiber_photometry_metadata["FiberPhotometryTable"]["rows"]
        assert list(rows.keys()) == ["row0", "row1"]
        assert [row["excitation_wavelength_in_nm"] for row in rows.values()] == [465.0, 405.0]
        assert all(row["emission_wavelength_in_nm"] == 525.0 for row in rows.values())
        assert all(row["location"] == "unknown" for row in rows.values())
        assert fiber_photometry_metadata["FiberPhotometryIndicators"]["indicator"]["label"] == "GCaMP"
        # The response series references every row.
        series_metadata = fiber_photometry_metadata[interface.metadata_key]
        assert series_metadata["fiber_photometry_table_region"] == ["row0", "row1"]

    def test_metadata_key_override(self):
        # An explicit metadata_key names the response-series entry instead of the stream-derived default.
        interface = MockFiberPhotometryInterface(metadata_key="my_series")
        assert interface.metadata_key == "my_series"
        assert "my_series" in interface.get_metadata()["FiberPhotometry"]

    def test_single_stream_collapses_to_one_channel(self):
        # A single stream exercises the base's shape[1] == 1 collapse: a 1-D series and a one-row table.
        interface = MockFiberPhotometryInterface(stream_names="signal", excitation_wavelengths_in_nm=(465.0,))
        nwbfile = interface.create_nwbfile()

        assert len(nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table) == 1
        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100,)

    def test_wavelength_stream_length_mismatch_errors(self):
        # One excitation wavelength per stream is required; a mismatch is a construction error.
        expected_error = "excitation_wavelengths_in_nm has 1 entries but there are 2 stream(s)"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            MockFiberPhotometryInterface(stream_names=["a", "b"], excitation_wavelengths_in_nm=(465.0,))

    def test_round_trip(self, tmp_path):
        # The mock's reason for existing: a fiber photometry file that writes and reads back with no data
        # on disk, so the ndx-fiber-photometry write/read path is covered without gin fixtures.
        interface = MockFiberPhotometryInterface(seed=1)
        expected_data = interface._read_response_data()

        nwbfile_path = tmp_path / "mock_fiber_photometry.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            series = nwbfile.acquisition["FiberPhotometryResponseSeries"]
            assert_array_equal(series.data[:], expected_data)
            assert len(nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table) == 2
