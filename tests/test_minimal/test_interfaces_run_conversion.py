"""Tests for the `run_conversion` methods of `BaseDataInterface` and `NWBConverter`."""

from datetime import datetime

import pytest
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, read_nwb

from neuroconv import NWBConverter
from neuroconv.tools.nwb_helpers import get_existing_backend_configuration
from neuroconv.tools.testing.mock_interfaces import MockTimeSeriesInterface


def written_dataset_settings(nwbfile) -> dict:
    """The dataset settings a written file actually carries, keyed by location, ignoring object identity."""
    backend_configuration = get_existing_backend_configuration(nwbfile=nwbfile)
    return {
        location: dataset_configuration.model_dump(exclude={"object_id"})
        for location, dataset_configuration in backend_configuration.dataset_configurations.items()
    }


def test_base_data_interface_append_on_disk(tmp_path):
    """Test that append_on_disk_nwbfile works for BaseDataInterface.run_conversion."""
    nwbfile_path = tmp_path / "test_append.nwb"

    # First write - create the file with first TimeSeries
    interface1 = MockTimeSeriesInterface(num_channels=3, duration=0.1, metadata_key="TimeSeriesFirst")
    metadata1 = interface1.get_metadata()
    metadata1["TimeSeries"]["TimeSeriesFirst"]["name"] = "TimeSeriesFirst"
    interface1.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata1)

    # Verify first interface data was written
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert "TimeSeriesFirst" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesFirst"].data.shape[1] == 3

    # Append to existing file with second interface (another TimeSeries)
    interface2 = MockTimeSeriesInterface(num_channels=2, duration=0.1, metadata_key="TimeSeriesSecond")
    metadata2 = interface2.get_metadata()
    metadata2["TimeSeries"]["TimeSeriesSecond"]["name"] = "TimeSeriesSecond"
    interface2.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata2, append_on_disk_nwbfile=True)

    # Verify both interfaces' data exists
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        # First TimeSeries
        assert "TimeSeriesFirst" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesFirst"].data.shape[1] == 3
        # Second TimeSeries
        assert "TimeSeriesSecond" in nwbfile.acquisition
        assert nwbfile.acquisition["TimeSeriesSecond"].data.shape[1] == 2


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_interface_backend_matches_default_backend_configuration(tmp_path, backend):
    """`backend=...` and the matching default `backend_configuration` write the same file.

    Passing `backend` makes `configure_and_write_nwbfile` derive the default configuration itself, so the
    two spellings differ only in who calls `get_default_backend_configuration`. This is the check that lets
    the interface test mixin write once per backend instead of twice.
    """
    interface = MockTimeSeriesInterface(num_channels=3, duration=0.1)
    metadata = interface.get_metadata()

    from_backend_path = tmp_path / f"from_backend_{backend}.nwb"
    interface.run_conversion(nwbfile_path=from_backend_path, metadata=metadata, backend=backend)

    from_configuration_path = tmp_path / f"from_backend_configuration_{backend}.nwb"
    nwbfile = interface.create_nwbfile(metadata=metadata)
    backend_configuration = interface.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    interface.run_conversion(
        nwbfile_path=from_configuration_path, metadata=metadata, backend_configuration=backend_configuration
    )

    from_backend = read_nwb(from_backend_path)
    from_configuration = read_nwb(from_configuration_path)

    assert written_dataset_settings(from_backend) == written_dataset_settings(from_configuration)
    assert_array_equal(
        from_backend.acquisition["TimeSeries"].data[:], from_configuration.acquisition["TimeSeries"].data[:]
    )

    from_backend.read_io.close()
    from_configuration.read_io.close()


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_converter_backend_matches_default_backend_configuration(tmp_path, backend):
    """`NWBConverter.run_conversion` accepts both spellings and writes the same file from either."""

    class TestConverter(NWBConverter):
        data_interface_classes = dict(Test=MockTimeSeriesInterface)

    converter = TestConverter(source_data=dict(Test=dict(num_channels=3, duration=0.1)))
    metadata = converter.get_metadata()
    if "session_start_time" not in metadata["NWBFile"]:
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1).astimezone())

    from_backend_path = tmp_path / f"converter_from_backend_{backend}.nwb"
    converter.run_conversion(nwbfile_path=from_backend_path, metadata=metadata, backend=backend)

    from_configuration_path = tmp_path / f"converter_from_backend_configuration_{backend}.nwb"
    nwbfile = converter.create_nwbfile(metadata=metadata)
    backend_configuration = converter.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    converter.run_conversion(
        nwbfile_path=from_configuration_path, metadata=metadata, backend_configuration=backend_configuration
    )

    from_backend = read_nwb(from_backend_path)
    from_configuration = read_nwb(from_configuration_path)

    assert written_dataset_settings(from_backend) == written_dataset_settings(from_configuration)
    assert_array_equal(
        from_backend.acquisition["TimeSeries"].data[:], from_configuration.acquisition["TimeSeries"].data[:]
    )

    from_backend.read_io.close()
    from_configuration.read_io.close()
