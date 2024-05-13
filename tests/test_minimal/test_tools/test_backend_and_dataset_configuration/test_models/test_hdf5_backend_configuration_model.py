"""Unit tests for the DatasetInfo Pydantic model."""

from io import StringIO
from unittest.mock import patch

from neuroconv.tools.nwb_helpers import HDF5BackendConfiguration
from neuroconv.tools.testing import mock_HDF5BackendConfiguration


def test_hdf5_backend_configuration_print():
    """Test the printout display of a HDF5BackendConfiguration model looks nice."""
    hdf5_backend_configuration = mock_HDF5BackendConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_backend_configuration)

    expected_print = """
HDF5 dataset configurations
---------------------------

acquisition/TestElectricalSeriesAP/data
---------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  expected RAM usage : 960.00 MB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip


acquisition/TestElectricalSeriesLF/data
---------------------------------------
  dtype : int16
  full shape of source array : (75000, 384)
  full size of source array : 57.60 MB

  buffer shape : (75000, 384)
  expected RAM usage : 57.60 MB

  chunk shape : (37500, 128)
  disk space usage per chunk : 9.60 MB

  compression method : gzip

"""
    assert out.getvalue() == expected_print


def test_hdf5_backend_configuration_schema():
    assert HDF5BackendConfiguration.schema() is not None
    assert HDF5BackendConfiguration.schema_json() is not None
    assert HDF5BackendConfiguration.model_json_schema() is not None
