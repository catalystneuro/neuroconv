"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface


class TestMockFiberPhotometryInterface:
    def test_get_metadata_adds_no_provenance(self):
        # The mock contributes only a session start time: location, wavelengths and the indicator label
        # describe a preparation a synthetic source does not have, so they are left to the user. What is
        # present here is the base's own scaffold, still holding its placeholder sentinels (see #1789).
        interface = MockFiberPhotometryInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        metadata = interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"].year == 2020

        rows = metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]
        assert all(row["location"] == "PLACEHOLDER" for row in rows.values())
        assert metadata["FiberPhotometry"]["FiberPhotometryIndicators"]["indicator"]["label"] == "PLACEHOLDER"

    def test_default_metadata_warns_about_placeholders(self):
        # Nothing fills the base scaffold's sentinels, so a default conversion warns like any real
        # interface would. PR B removes the scaffold and this warning with it.
        interface = MockFiberPhotometryInterface()
        with pytest.warns(UserWarning, match="placeholder"):
            interface.create_nwbfile()

    def test_metadata_key_override(self):
        # An explicit metadata_key names the response-series entry instead of the stream-derived default.
        interface = MockFiberPhotometryInterface(metadata_key="my_series")
        assert interface.metadata_key == "my_series"
        assert "my_series" in interface.get_metadata()["FiberPhotometry"]

    def test_single_stream_collapses_to_one_channel(self):
        # A single stream exercises the base's shape[1] == 1 collapse, giving a 1-D series.
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
