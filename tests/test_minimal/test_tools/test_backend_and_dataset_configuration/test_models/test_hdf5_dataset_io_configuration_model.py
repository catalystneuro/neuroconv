"""Unit tests for the HDF5DatasetIOConfiguration Pydantic model."""

from io import StringIO
from unittest.mock import patch

import numpy as np
import pytest
from pydantic import ValidationError

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5DatasetIOConfiguration,
)
from neuroconv.tools.testing import mock_HDF5DatasetIOConfiguration


def test_hdf5_dataset_configuration_print():
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

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

  compressors : ['gzip']

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_options():
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressor_options=[dict(level=5)])

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

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

  compressors : ['gzip']
  compressor options : [{'level': 5}]

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_disabled():
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressors=None)

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

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

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_repr():
    """Test the programmatic repr of a HDF5DatasetIOConfiguration model is more dataclass-like."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    # Important to keep the `repr` unmodified for appearance inside iterables of DatasetInfo objects
    expected_repr = (
        "HDF5DatasetIOConfiguration(object_id='481a0860-3a0c-40ec-b931-df4a3e9b101f', "
        "location_in_file='acquisition/TestElectricalSeries/data', dataset_name='data', dtype=dtype('int16'), "
        "full_shape=(1800000, 384), chunk_shape=(78125, 64), buffer_shape=(1250000, 384), compressors=['gzip'], "
        "compressor_options=None)"
    )
    assert repr(hdf5_dataset_configuration) == expected_repr


def test_available_hdf5_compression_methods_not_empty():
    assert len(AVAILABLE_HDF5_COMPRESSION_METHODS) > 0


def test_default_compression_is_always_available():
    assert "gzip" in AVAILABLE_HDF5_COMPRESSION_METHODS


def test_get_data_io_kwargs():
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    assert hdf5_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compression="gzip", compression_opts=None
    )


def test_hdf5_dataset_io_configuration_schema():
    assert HDF5DatasetIOConfiguration.schema() is not None
    assert HDF5DatasetIOConfiguration.schema_json() is not None
    assert HDF5DatasetIOConfiguration.model_json_schema() is not None


def test_get_data_io_kwargs_with_shuffle():
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressors=["shuffle", "gzip"])

    assert hdf5_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compression="gzip", compression_opts=None, shuffle=True
    )


def test_get_data_io_kwargs_with_shuffle_and_fletcher32():
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressors=["shuffle", "gzip", "fletcher32"])

    assert hdf5_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compression="gzip", compression_opts=None, shuffle=True, fletcher32=True
    )


def test_get_data_io_kwargs_with_filter_but_no_compression_method():
    """A filter composes with a compression method, so naming one without a method leaves compression disabled."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressors=["shuffle"])

    data_io_kwargs = hdf5_dataset_configuration.get_data_io_kwargs()

    assert data_io_kwargs["chunks"] == (78125, 64)
    assert data_io_kwargs["shuffle"] is True
    # The two branches of `get_data_io_kwargs` disable compression differently; either way it is off
    assert not data_io_kwargs["compression"]


def test_compressors_out_of_order_raises():
    with pytest.raises(ValidationError, match="HDF5 fixes the order of its filter pipeline"):
        mock_HDF5DatasetIOConfiguration(compressors=["gzip", "shuffle"])


def test_fletcher32_before_compression_method_raises():
    with pytest.raises(ValidationError, match="HDF5 fixes the order of its filter pipeline"):
        mock_HDF5DatasetIOConfiguration(compressors=["fletcher32", "gzip"])


def test_more_than_one_compression_method_raises():
    with pytest.raises(ValidationError, match="HDF5 accepts at most one compression method per dataset"):
        mock_HDF5DatasetIOConfiguration(compressors=["gzip", "lzf"])


def test_repeated_filter_raises():
    with pytest.raises(ValidationError, match="The 'shuffle' filter can only appear once"):
        mock_HDF5DatasetIOConfiguration(compressors=["shuffle", "shuffle", "gzip"])


def test_compressor_options_length_mismatch_raises():
    with pytest.raises(ValidationError, match="Length mismatch between `compressors`"):
        mock_HDF5DatasetIOConfiguration(compressors=["shuffle", "gzip"], compressor_options=[None])


def test_deprecated_compression_method_argument():
    """`compression_method` remains accepted for one release cycle and maps onto `compressors`."""
    with pytest.warns(FutureWarning, match="removed in v0.12.0"):
        hdf5_dataset_configuration = HDF5DatasetIOConfiguration(
            object_id="481a0860-3a0c-40ec-b931-df4a3e9b101f",
            location_in_file="acquisition/TestElectricalSeries/data",
            dataset_name="data",
            full_shape=(60 * 30_000, 384),
            dtype=np.dtype("int16"),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            compression_method="lzf",
        )

    assert hdf5_dataset_configuration.compressors == ["lzf"]


def test_deprecated_compression_method_property():
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compressors=["shuffle", "gzip"])

    with pytest.warns(FutureWarning, match="removed in v0.12.0"):
        assert hdf5_dataset_configuration.compression_method == "gzip"

    with pytest.warns(FutureWarning, match="removed in v0.12.0"):
        hdf5_dataset_configuration.compression_method = "lzf"

    # Setting the compression method leaves the filters that compose with it in place
    assert hdf5_dataset_configuration.compressors == ["shuffle", "lzf"]


def test_specifying_both_spellings_raises():
    with pytest.raises(ValidationError, match="Use only `compressors` and `compressor_options`"):
        HDF5DatasetIOConfiguration(
            object_id="481a0860-3a0c-40ec-b931-df4a3e9b101f",
            location_in_file="acquisition/TestElectricalSeries/data",
            dataset_name="data",
            full_shape=(60 * 30_000, 384),
            dtype=np.dtype("int16"),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            compression_method="gzip",
            compressors=["gzip"],
        )
