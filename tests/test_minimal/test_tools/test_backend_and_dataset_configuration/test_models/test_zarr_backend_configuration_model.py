"""Unit tests for the DatasetInfo Pydantic model."""

from io import StringIO
from unittest.mock import patch

from neuroconv.tools.testing import mock_ZarrBackendConfiguration


def test_zarr_backend_configuration_print():
    """Test the printout display of a ZarrBackendConfiguration model looks nice."""
    zarr_backend_configuration = mock_ZarrBackendConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_backend_configuration)

    expected_print = """
Configurable datasets identified using the zarr backend
-------------------------------------------------------

acquisition/TestElectricalSeriesAP/data
---------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.29 GiB

  buffer shape : (1250000, 384)
  expected RAM usage : 915.53 MiB

  chunk shape : (78125, 64)
  disk space usage per chunk : 9.54 MiB

  compression method : gzip

  filter methods : ['delta']


acquisition/TestElectricalSeriesLF/data
---------------------------------------
  dtype : int16
  full shape of source array : (75000, 384)
  full size of source array : 54.93 MiB

  buffer shape : (75000, 384)
  expected RAM usage : 54.93 MiB

  chunk shape : (37500, 128)
  disk space usage per chunk : 9.16 MiB

  compression method : gzip

  filter methods : ['delta']

"""
    assert out.getvalue() == expected_print
