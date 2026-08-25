"""Unit tests for `configure_backend` on an already written file open in append mode."""

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, read_nwb
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    configure_backend,
    get_default_backend_configuration,
)

EXISTING_ARRAY = np.array([[1, 2, 3], [4, 5, 6]], dtype="int16")
APPENDED_ARRAY = np.array([[7, 8, 9], [10, 11, 12]], dtype="int16")


@pytest.fixture
def nwbfile_path(tmp_path) -> str:
    """Path to an hdf5 file holding a single, unconfigured TimeSeries."""
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(mock_TimeSeries(name="ExistingTimeSeries", data=EXISTING_ARRAY))

    nwbfile_path = str(tmp_path / "test_configure_backend_appended_file.nwb")
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    return nwbfile_path


def test_appended_time_series(nwbfile_path: str):
    """The configuration of an appended dataset reaches the file it is appended to.

    Appending writes through the same IO that read the file, so the builder `configure_backend` inspects must
    not be the one that IO will write; a builder cached before the `DataIO` wrapping would be written in its
    place, silently dropping the compression. Zarr has no append mode, so this is hdf5 only.
    """
    with NWBHDF5IO(path=nwbfile_path, mode="r+", load_namespaces=True) as io:
        nwbfile = io.read()
        nwbfile.add_acquisition(mock_TimeSeries(name="AppendedTimeSeries", data=APPENDED_ARRAY))

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

        io.write(nwbfile)

    written_nwbfile = read_nwb(nwbfile_path)

    written_data = written_nwbfile.acquisition["AppendedTimeSeries"].data
    assert written_data.compression == "gzip"
    assert written_data.chunks == APPENDED_ARRAY.shape
    assert_array_equal(written_data[:], APPENDED_ARRAY)

    assert_array_equal(written_nwbfile.acquisition["ExistingTimeSeries"].data[:], EXISTING_ARRAY)
    written_nwbfile.read_io.close()
