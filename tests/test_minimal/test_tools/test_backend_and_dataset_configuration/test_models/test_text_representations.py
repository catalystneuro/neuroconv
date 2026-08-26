"""
Tests for how the configuration models render themselves as text.

These assert appearance, not conduct. They live apart from the functional tests so that a change to
the printout is obviously a change to the printout, and so that nobody reads a failure here as a
defect in what gets written to disk. `repr` is deliberately not asserted anywhere: it is Pydantic's
and pinning it character for character buys nothing.
"""

from neuroconv.tools.testing import (
    mock_HDF5BackendConfiguration,
    mock_HDF5DatasetIOConfiguration,
    mock_ZarrBackendConfiguration,
    mock_ZarrDatasetIOConfiguration,
)
from neuroconv.utils.str_utils import human_readable_size


def test_hdf5_dataset_configuration_print():
    """The printout of a HDF5DatasetIOConfiguration reads well."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  expected RAM usage : 960.00 MB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip
"""
    assert str(hdf5_dataset_configuration) == expected_print


def test_zarr_dataset_configuration_print():
    """The printout of a ZarrDatasetIOConfiguration reads well."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration()

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  expected RAM usage : 960.00 MB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip
"""
    assert str(zarr_dataset_configuration) == expected_print


def test_hdf5_backend_configuration_print():
    """The printout of a HDF5BackendConfiguration nests one dataset printout per configured dataset."""
    hdf5_backend_configuration = mock_HDF5BackendConfiguration()

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
    assert str(hdf5_backend_configuration) == expected_print


def test_zarr_backend_configuration_print():
    """The printout of a ZarrBackendConfiguration also renders the filter methods."""
    zarr_backend_configuration = mock_ZarrBackendConfiguration()

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
    assert str(zarr_backend_configuration) == expected_print


def test_hdf5_dataset_configuration_print_omits_unset_compression():
    """An unset field renders as no line at all, not as a line reading `None`."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_method=None)

    printout = str(hdf5_dataset_configuration)

    assert "compression method" not in printout
    assert "compression options" not in printout


def test_zarr_dataset_configuration_print_omits_unset_compression_and_filters():
    """An unset field renders as no line at all, not as a line reading `None`."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compression_method=None)

    printout = str(zarr_dataset_configuration)

    assert "compression method" not in printout
    assert "compression options" not in printout
    assert "filter methods" not in printout
    assert "filter options" not in printout


def test_printout_reports_the_derived_sizes():
    """The printout is a rendering of the properties, so the two cannot drift apart."""
    dataset_configuration = mock_HDF5DatasetIOConfiguration()

    printout = str(dataset_configuration)

    assert f"full size of source array : {human_readable_size(dataset_configuration.full_size_in_bytes)}" in printout
    assert (
        f"expected RAM usage : {human_readable_size(dataset_configuration.maximum_ram_usage_per_iteration_in_bytes)}"
        in printout
    )
    assert (
        "disk space usage per chunk : "
        f"{human_readable_size(dataset_configuration.disk_space_usage_per_chunk_in_bytes)}" in printout
    )
