"""Unit tests for the DatasetInfo Pydantic model."""
from io import StringIO
from unittest.mock import patch

from neuroconv.tools.testing import mock_HDF5BackendConfiguration


def test_hdf5_backend_configuration_print():
    """Test the printout display of a HDF5BackendConfiguration model looks nice."""
    hdf5_backend_configuration = mock_HDF5BackendConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_backend_configuration)

    expected_print = """
Configurable datasets identified using the hdf5 backend
-------------------------------------------------------

acquisition/TestElectricalSeriesAP/data
---------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  maximum RAM usage per iteration : 0.96 GB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip


acquisition/TestElectricalSeriesLF/data
---------------------------------------
  dtype : int16
  full shape of source array : (75000, 384)
  full size of source array : 0.06 GB

  buffer shape : (75000, 384)
  maximum RAM usage per iteration : 0.06 GB

  chunk shape : (37500, 128)
  disk space usage per chunk : 9.60 MB

  compression method : gzip

"""
    assert out.getvalue() == expected_print
