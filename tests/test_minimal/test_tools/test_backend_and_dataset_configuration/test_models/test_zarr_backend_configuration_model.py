"""Unit tests for the DatasetInfo Pydantic model."""

from io import StringIO
from unittest.mock import patch

from neuroconv.tools.nwb_helpers import ZarrBackendConfiguration
from neuroconv.tools.testing import mock_ZarrBackendConfiguration


def test_zarr_backend_configuration_print():
    """Test the printout display of a ZarrBackendConfiguration model looks nice."""
    zarr_backend_configuration = mock_ZarrBackendConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_backend_configuration)

    expected_print = """
Zarr dataset configurations
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

  filter methods : ['delta']


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

  filter methods : ['delta']

"""
    assert out.getvalue() == expected_print


def test_zarr_backend_configuration_schema():
    assert ZarrBackendConfiguration.schema() is not None
    assert ZarrBackendConfiguration.schema_json() is not None
    assert ZarrBackendConfiguration.model_json_schema() is not None
