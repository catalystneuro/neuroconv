from typing import Any, Iterable, Literal, Union

import h5py
import numcodecs
import numpy as np

from ...nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    HDF5BackendConfiguration,
    HDF5DatasetIOConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetIOConfiguration,
)


def mock_HDF5DatasetIOConfiguration(
    object_id: str = "481a0860-3a0c-40ec-b931-df4a3e9b101f",
    location_in_file: str = "acquisition/TestElectricalSeries/data",
    dataset_name: Literal["data", "timestamps"] = "data",
    full_shape: tuple[int, ...] = (60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
    dtype: np.dtype = np.dtype("int16"),
    chunk_shape: tuple[int, ...] = (78_125, 64),  # ~10 MB
    buffer_shape: tuple[int, ...] = (1_250_000, 384),  # ~1 GB
    compression_method: Union[
        Literal[tuple(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())], h5py._hl.filters.FilterRefBase, None
    ] = "gzip",
    compression_options: Union[dict[str, Any], None] = None,
) -> HDF5DatasetIOConfiguration:
    """Mock object of a HDF5DatasetIOConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return HDF5DatasetIOConfiguration(
        object_id=object_id,
        location_in_file=location_in_file,
        dataset_name=dataset_name,
        full_shape=full_shape,
        dtype=dtype,
        chunk_shape=chunk_shape,
        buffer_shape=buffer_shape,
        compression_method=compression_method,
        compression_options=compression_options,
    )


def mock_ZarrDatasetIOConfiguration(
    object_id: str = "481a0860-3a0c-40ec-b931-df4a3e9b101f",
    location_in_file: str = "acquisition/TestElectricalSeries/data",
    dataset_name: Literal["data", "timestamps"] = "data",
    full_shape: tuple[int, ...] = (60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
    dtype: np.dtype = np.dtype("int16"),
    chunk_shape: tuple[int, ...] = (78_125, 64),  # ~10 MB
    buffer_shape: tuple[int, ...] = (1_250_000, 384),  # ~1 GB
    compression_method: Union[
        Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None
    ] = "gzip",
    compression_options: Union[dict[str, Any]] = None,
    filter_methods: Iterable[
        Union[Literal[tuple(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())], numcodecs.abc.Codec, None]
    ] = None,
    filter_options: Union[Iterable[dict[str, Any]], None] = None,
) -> ZarrDatasetIOConfiguration:
    """Mock object of a ZarrDatasetIOConfiguration with NeuroPixel-like values to show chunk/buffer recommendations."""
    return ZarrDatasetIOConfiguration(
        object_id=object_id,
        location_in_file=location_in_file,
        dataset_name=dataset_name,
        full_shape=full_shape,
        dtype=dtype,
        chunk_shape=chunk_shape,
        buffer_shape=buffer_shape,
        compression_method=compression_method,
        compression_options=compression_options,
        filter_methods=filter_methods,
        filter_options=filter_options,
    )


def mock_HDF5BackendConfiguration() -> HDF5BackendConfiguration:
    """Mock instance of a HDF5BackendConfiguration with two NeuroPixel-like datasets."""
    dataset_configurations: dict[str, HDF5DatasetIOConfiguration] = {
        "acquisition/TestElectricalSeriesAP/data": mock_HDF5DatasetIOConfiguration(
            location_in_file="acquisition/TestElectricalSeriesAP/data", dataset_name="data"
        ),
        "acquisition/TestElectricalSeriesLF/data": mock_HDF5DatasetIOConfiguration(
            object_id="bc37e164-519f-4b65-a976-206440f1d325",
            location_in_file="acquisition/TestElectricalSeriesLF/data",
            dataset_name="data",
            full_shape=(75_000, 384),
            chunk_shape=(37_500, 128),  # ~10 MB
            buffer_shape=(75_000, 384),
        ),
    }

    return HDF5BackendConfiguration(
        dataset_configurations=dataset_configurations,
    )


def mock_ZarrBackendConfiguration() -> ZarrBackendConfiguration:
    """Mock instance of a HDF5BackendConfiguration with several NeuroPixel-like datasets."""
    dataset_configurations: dict[str, ZarrDatasetIOConfiguration] = {
        "acquisition/TestElectricalSeriesAP/data": mock_ZarrDatasetIOConfiguration(
            location_in_file="acquisition/TestElectricalSeriesAP/data",
            dataset_name="data",
            filter_methods=["delta"],
        ),
        "acquisition/TestElectricalSeriesLF/data": mock_ZarrDatasetIOConfiguration(
            object_id="bc37e164-519f-4b65-a976-206440f1d325",
            location_in_file="acquisition/TestElectricalSeriesLF/data",
            dataset_name="data",
            full_shape=(75_000, 384),
            chunk_shape=(37_500, 128),  # ~10 MB
            buffer_shape=(75_000, 384),
            filter_methods=["delta"],
        ),
    }

    return ZarrBackendConfiguration(dataset_configurations=dataset_configurations)
