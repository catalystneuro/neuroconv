"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Iterable, Literal, Union

import h5py
import numpy as np
import zarr
from hdmf import Container
from hdmf.data_utils import DataChunkIterator, DataIO, GenericDataChunkIterator
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.base import DynamicTable

from ._dataset_and_backend_models import (
    BACKEND_TO_CONFIGURATION,
    BACKEND_TO_DATASET_CONFIGURATION,
    DatasetConfiguration,
    DatasetInfo,
    HDF5BackendConfiguration,
    HDF5DatasetConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetConfiguration,
)
from ..hdmf import SliceableDataChunkIterator


def _get_mode(io: Union[NWBHDF5IO, NWBZarrIO]) -> str:
    """NWBHDF5IO and NWBZarrIO have different ways of storing the mode they used on a path."""
    if isinstance(io, NWBHDF5IO):
        return io.mode
    elif isinstance(io, NWBZarrIO):
        return io._ZarrIO__mode


def _is_value_already_written_to_file(
    candidate_dataset: Union[h5py.Dataset, zarr.Array],
    backend: Literal["hdf5", "zarr"],
    existing_file: Union[h5py.File, zarr.Group, None],
) -> bool:
    """
    Determine if the neurodata object is already written to the file on disk.

    This object should then be skipped by the `get_io_datasets` function when working in append mode.
    """
    return (
        isinstance(candidate_dataset, h5py.Dataset)  # If the source data is an HDF5 Dataset
        and backend == "hdf5"  # If working in append mode
        and candidate_dataset.file == existing_file  # If the source HDF5 Dataset is the appending NWBFile
    ) or (
        isinstance(candidate_dataset, zarr.Array)  # If the source data is an Zarr Array
        and backend == "zarr"  # If working in append mode
        and candidate_dataset.store == existing_file  # If the source Zarr 'file' is the appending NWBFile
    )


def _parse_location_in_memory_nwbfile(current_location: str, neurodata_object: Container) -> str:
    parent = neurodata_object.parent
    if isinstance(parent, NWBFile):
        # Items in defined top-level places like acquisition, intervals, etc. do not act as 'containers'
        # in the .parent sense; ask if object is in their in-memory dictionaries instead
        for outer_field_name, outer_field_value in parent.fields.items():
            if isinstance(outer_field_value, dict) and neurodata_object.name in outer_field_value:
                return outer_field_name + "/" + neurodata_object.name + "/" + current_location
        return neurodata_object.name + "/" + current_location
    return _parse_location_in_memory_nwbfile(
        current_location=neurodata_object.name + "/" + current_location, neurodata_object=parent
    )


def _get_dataset_metadata(
    neurodata_object: Union[TimeSeries, DynamicTable], field_name: str, backend: Literal["hdf5", "zarr"]
) -> Union[HDF5DatasetConfiguration, ZarrDatasetConfiguration]:
    """Fill in the Dataset model with as many values as can be automatically detected or inferred."""
    DatasetConfigurationClass = BACKEND_TO_DATASET_CONFIGURATION[backend]

    candidate_dataset = getattr(neurodata_object, field_name)
    # For now, skip over datasets already wrapped in DataIO
    # Could maybe eventually support modifying chunks in place
    # But setting buffer shape only possible if iterator was wrapped first
    if not isinstance(candidate_dataset, DataIO):
        # DataChunkIterator has best generic dtype inference, though logic is hard to peel out of it
        # And it can fail in rare cases but not essential to our default configuration
        try:
            dtype = str(DataChunkIterator(candidate_dataset).dtype)  # string cast to be JSON friendly
        except Exception as exception:
            if str(exception) != "Data type could not be determined. Please specify dtype in DataChunkIterator init.":
                raise exception
            else:
                dtype = "unknown"

        maxshape = get_data_shape(data=candidate_dataset)

        if isinstance(candidate_dataset, GenericDataChunkIterator):
            chunk_shape = candidate_dataset.chunk_shape
            buffer_shape = candidate_dataset.buffer_shape
        elif dtype != "unknown":
            # TODO: eventually replace this with staticmethods on hdmf.data_utils.GenericDataChunkIterator
            chunk_shape = SliceableDataChunkIterator.estimate_default_chunk_shape(
                chunk_mb=10.0, maxshape=maxshape, dtype=np.dtype(dtype)
            )
            buffer_shape = SliceableDataChunkIterator.estimate_default_buffer_shape(
                buffer_gb=0.5, chunk_shape=chunk_shape, maxshape=maxshape, dtype=np.dtype(dtype)
            )
        else:
            pass  # TODO: think on this; perhaps zarr's standalone estimator?

        dataset_info = DatasetInfo(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            location=_parse_location_in_memory_nwbfile(current_location=field_name, neurodata_object=neurodata_object),
            field=field_name,
            maxshape=maxshape,
            dtype=dtype,
        )
        dataset_configuration = DatasetConfigurationClass(
            dataset_info=dataset_info, chunk_shape=chunk_shape, buffer_shape=buffer_shape
        )
        return dataset_configuration


def get_default_dataset_configurations(
    nwbfile: NWBFile,
    backend: Union[None, Literal["hdf5", "zarr"]] = None,  # None for auto-detect from append mode, otherwise required
) -> Iterable[DatasetConfiguration]:
    """
    Method for automatically detecting all objects in the file that could be wrapped in a DataIO.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        An in-memory NWBFile object, either generated from the base class or read from an existing file of any backend.
    backend : "hdf5" or "zarr"
        Which backend format type you would like to use in configuring each datasets compression methods and options.

    Yields
    ------
    DatasetConfiguration
        A summary of each detected object that can be wrapped in a DataIO.
    """
    if backend is None and nwbfile.read_io is None:
        raise ValueError(
            "Keyword argument `backend` (either 'hdf5' or 'zarr') must be specified if the `nwbfile` was not "
            "read from an existing file!"
        )
    if backend is None and nwbfile.read_io is not None and nwbfile.read_io.mode not in ("r+", "a"):
        raise ValueError(
            "Keyword argument `backend` (either 'hdf5' or 'zarr') must be specified if the `nwbfile` is being appended."
        )

    detected_backend = None
    existing_file = None
    if isinstance(nwbfile.read_io, NWBHDF5IO) and _get_mode(io=nwbfile.read_io) in ("r+", "a"):
        detected_backend = "hdf5"
        existing_file = nwbfile.read_io._file
    elif isinstance(nwbfile.read_io, NWBZarrIO) and _get_mode(io=nwbfile.read_io) in ("r+", "a"):
        detected_backend = "zarr"
        existing_file = nwbfile.read_io.file.store
    backend = backend or detected_backend

    if detected_backend is not None and detected_backend != backend:
        raise ValueError(
            f"Detected backend '{detected_backend}' for appending file, but specified `backend` "
            f"({backend}) does not match! Set `backend=None` or remove the keyword argument to allow it to auto-detect."
        )

    for neurodata_object in nwbfile.objects.values():
        if isinstance(neurodata_object, TimeSeries):
            time_series = neurodata_object  # for readability

            for field_name in ("data", "timestamps"):
                if field_name not in time_series.fields:  # timestamps is optional
                    continue

                candidate_dataset = getattr(time_series, field_name)
                if _is_value_already_written_to_file(
                    candidate_dataset=candidate_dataset, backend=backend, existing_file=existing_file
                ):
                    continue  # skip

                # Edge case of in-memory ImageSeries with external mode; data is in fields and is empty array
                if isinstance(candidate_dataset, np.ndarray) and not np.any(candidate_dataset):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=time_series, field_name=field_name, backend=backend)
        elif isinstance(neurodata_object, DynamicTable):
            dynamic_table = neurodata_object  # for readability

            for column_name in dynamic_table.colnames:
                candidate_dataset = dynamic_table[column_name].data  # VectorData object
                if _is_value_already_written_to_file(
                    candidate_dataset=candidate_dataset, backend=backend, existing_file=existing_file
                ):
                    continue  # skip

                yield _get_dataset_metadata(
                    neurodata_object=dynamic_table[column_name], field_name="data", backend=backend
                )


def get_default_backend_configuration(
    nwbfile: NWBFile, backend: Literal["hdf5", "zarr"]
) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
    """Fill a default backend configuration to serve as a starting point for further customization."""
    BackendConfigurationClass = BACKEND_TO_CONFIGURATION[backend]

    default_dataset_configurations = get_default_dataset_configurations(nwbfile=nwbfile, backend=backend)
    dataset_configurations = {
        default_dataset_configuration.dataset_info.location: default_dataset_configuration
        for default_dataset_configuration in default_dataset_configurations
    }

    backend_configuration = BackendConfigurationClass(dataset_configurations=dataset_configurations)
    return backend_configuration


def configure_backend(
    nwbfile: NWBFile, backend_configuration: Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
) -> None:
    """Configure all datasets specified in the `backend_configuration` with their appropriate DataIO and options."""
    nwbfile_objects = nwbfile.objects.items()

    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.datset_configurations:
        object_id = dataset_configuration.dataset_info.object_id
        dataset_name = dataset_configuration.dataset_info.location.strip("/")[-1]
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        nwbfile_objects[object_id].set_data_io(dataset_name=dataset_name, data_io_class=data_io_class, **data_io_kwargs)
