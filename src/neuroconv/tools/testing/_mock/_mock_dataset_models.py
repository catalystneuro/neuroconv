from typing import Any, Dict, Iterable, Literal, Tuple, Union

import h5py
import numcodecs
import numpy as np

from ...nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    DatasetInfo,
    HDF5BackendConfiguration,
    HDF5DatasetIOConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetIOConfiguration,
)


def mock_DatasetInfo(
    object_id: str = "481a0860-3a0c-40ec-b931-df4a3e9b101f",
    location: str = "acquisition/TestElectricalSeries/data",
    full_shape: Tuple[int, ...] = (60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
    dtype=np.dtype("int16"),
) -> DatasetInfo:
    """Mock instance of a DatasetInfo with NeuroPixel-like values to showcase chunk/buffer recommendations."""
    return DatasetInfo(
        object_id=object_id,
        location=location,
        full_shape=full_shape,
        dtype=dtype,
    )


def mock_HDF5DatasetIOConfiguration(
    compression_method: Union[
        Literal[tuple(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())], h5py._hl.filters.FilterRefBase, None
    ] = "gzip",
    compression_options: Union[Dict[str, Any], None] = None,
) -> HDF5DatasetIOConfiguration:
    """Mock object of a HDF5DatasetIOConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return HDF5DatasetIOConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),  # ~10 MB
        buffer_shape=(1_250_000, 384),  # ~1 GB
        compression_method=compression_method,
        compression_options=compression_options,
    )


def mock_ZarrDatasetIOConfiguration(
    compression_method: Union[
        Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None
    ] = "gzip",
    compression_options: Union[Dict[str, Any]] = None,
    filter_methods: Iterable[
        Union[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None]
    ] = None,
    filter_options: Union[Iterable[Dict[str, Any]], None] = None,
) -> ZarrDatasetIOConfiguration:
    """Mock object of a ZarrDatasetIOConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return ZarrDatasetIOConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),  # ~10 MB
        buffer_shape=(1_250_000, 384),  # ~1 GB
        compression_method=compression_method,
        compression_options=compression_options,
        filter_methods=filter_methods,
        filter_options=filter_options,
    )


def mock_HDF5BackendConfiguration() -> HDF5BackendConfiguration:
    """Mock instance of a HDF5BackendConfiguration with two NeuroPixel-like datasets."""
    dataset_configurations = {
        "acquisition/TestElectricalSeriesAP/data": HDF5DatasetIOConfiguration(
            dataset_info=mock_DatasetInfo(location="acquisition/TestElectricalSeriesAP/data"),
            chunk_shape=(78_125, 64),  # ~10 MB
            buffer_shape=(1_250_000, 384),  # ~1 GB
        ),
        "acquisition/TestElectricalSeriesLF/data": HDF5DatasetIOConfiguration(
            dataset_info=mock_DatasetInfo(
                object_id="bc37e164-519f-4b65-a976-206440f1d325",
                location="acquisition/TestElectricalSeriesLF/data",
                full_shape=(75_000, 384),
            ),
            chunk_shape=(37_500, 128),  # ~10 MB
            buffer_shape=(75_000, 384),
        ),
    }

    return HDF5BackendConfiguration(dataset_configurations=dataset_configurations)


def mock_ZarrBackendConfiguration() -> ZarrBackendConfiguration:
    """Mock instance of a HDF5BackendConfiguration with several NeuroPixel-like datasets."""
    dataset_configurations = {
        "acquisition/TestElectricalSeriesAP/data": ZarrDatasetIOConfiguration(
            dataset_info=mock_DatasetInfo(location="acquisition/TestElectricalSeriesAP/data"),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),  # ~1 GB
            filter_methods=["delta"],
        ),
        "acquisition/TestElectricalSeriesLF/data": ZarrDatasetIOConfiguration(
            dataset_info=mock_DatasetInfo(
                object_id="bc37e164-519f-4b65-a976-206440f1d325",
                location="acquisition/TestElectricalSeriesLF/data",
                full_shape=(75_000, 384),
            ),
            chunk_shape=(37_500, 128),  # ~10 MB
            buffer_shape=(75_000, 384),
            filter_methods=["delta"],
        ),
    }

    return ZarrBackendConfiguration(dataset_configurations=dataset_configurations)
