from typing import Any, Dict, Iterable, Literal, Tuple, Union

import h5py
import numcodecs
import numpy as np

from ...nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    DatasetInfo,
    HDF5DatasetConfiguration,
    ZarrDatasetConfiguration,
)


def mock_DatasetInfo() -> DatasetInfo:
    """Mock instance of a DatasetInfo with NeuroPixel-like values to showcase chunk/buffer recommendations."""
    return DatasetInfo(
        object_id="481a0860-3a0c-40ec-b931-df4a3e9b101f",
        location="acquisition/TestElectricalSeries/data",
        full_shape=(60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
        dtype=np.dtype("int16"),
    )


def mock_HDF5DatasetConfiguration(
    compression_method: Union[
        Literal[tuple(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())], h5py._hl.filters.FilterRefBase, None
    ] = "gzip",
    compression_options: Union[Dict[str, Any], None] = None,
) -> HDF5DatasetConfiguration:
    """Mock instance of a HDF5DatasetConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return HDF5DatasetConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),  # ~10 MB
        buffer_shape=(1_250_000, 384),  # ~1 GB
        compression_method=compression_method,
        compression_options=compression_options,
    )


def mock_ZarrDatasetConfiguration(
    compression_method: Union[
        Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None
    ] = "gzip",
    compression_options: Union[Dict[str, Any]] = None,
    filter_methods: Iterable[
        Union[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None]
    ] = None,
    filter_options: Union[Iterable[Dict[str, Any]], None] = None,
) -> ZarrDatasetConfiguration:
    """Mock instance of a ZarrDatasetConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return ZarrDatasetConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),  # ~10 MB
        buffer_shape=(1_250_000, 384),  # ~1 GB
        compression_method=compression_method,
        compression_options=compression_options,
        filter_methods=filter_methods,
        filter_options=filter_options,
    )
