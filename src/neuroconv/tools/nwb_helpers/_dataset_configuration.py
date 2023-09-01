"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Iterable, Literal, Union

import h5py
import zarr
import numpy as np
from hdmf.data_utils import DataIO, GenericDataChunkIterator, DataChunkIterator
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.base import DynamicTable

from ..hdmf import SliceableDataChunkIterator
from ._dataset_and_backend_models import (
    ConfigurableDataset,
    DatasetConfiguration,
    HDF5BackendConfiguration,
    HDF5DatasetConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetConfiguration,
)


def _is_value_already_written_to_file(
    candidate_dataset: Union[h5py.Dataset, zarr.Array],
    backend_type: Literal["hdf5", "zarr"],
    existing_file: Union[h5py.File, zarr.Group, None],
) -> bool:
    """
    Determine if the neurodata object is already written to the file on disk.

    This object should then be skipped by the `get_io_datasets` function when working in append mode.
    """
    return (
        isinstance(candidate_dataset, h5py.Dataset)  # If the source data is an HDF5 Dataset
        and backend_type == "hdf5"  # If working in append mode
        and candidate_dataset.file == existing_file  # If the source HDF5 Dataset is the appending NWBFile
    ) or (
        isinstance(candidate_dataset, zarr.Array)  # If the source data is an Zarr Array
        and backend_type == "zarr"  # If working in append mode
        and candidate_dataset.store == existing_file  # If the source Zarr 'file' is the appending NWBFile
    )


def _get_dataset_metadata(neurodata_object: Union[TimeSeries, DynamicTable], field_name: str) -> DatasetConfiguration:
    """Fill in the Dataset model with as many values as can be automatically detected or inferred."""
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
            chunk_shape = SliceableDataChunkIterator.estimate_chunk_shape(chunk_mb=10.0, maxshape=maxshape, dtype=dtype)
            buffer_shape = SliceableDataChunkIterator.estimate_buffer_shape(
                buffer_gb=0.5, chunk_shape=chunk_shape, maxshape=maxshape, dtype=dtype
            )
        else:
            pass  # TODO: think on this; perhaps zarr's standalone estimator?

        return DatasetConfiguration(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            parent=neurodata_object.get_ancestor().name,  # or should this be full location relative to root?
            field=field_name,
            chunk_shape=chunk_shape,
            buffer_shape=buffer_shape,
            maxshape=maxshape,
            dtype=dtype,
        )


def get_configurable_datasets(nwbfile: NWBFile) -> Iterable[DatasetConfiguration]:
    """
    Method for automatically detecting all objects in the file that could be wrapped in a DataIO.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        An in-memory NWBFile object, either generated from the base class or read from an existing file of any backend.

    Yields
    ------
    ConfigurableDataset
        A summary of each detected object that can be wrapped in a DataIO.
    """
    backend_type = None  # Used for filtering out datasets that have already been written to disk when appending
    existing_file = None
    if isinstance(nwbfile.read_io, NWBHDF5IO):
        backend_type = "hdf5"
        existing_file = nwbfile.read_io._file
    elif isinstance(nwbfile.read_io, NWBZarrIO):
        backend_type = "zarr"
        existing_file = nwbfile.read_io.file.store

    for _, neurodata_object in nwbfile.objects.items():
        # TODO: edge case of ImageSeries with external file mode?
        if isinstance(neurodata_object, TimeSeries):
            time_series = neurodata_object  # for readability

            for field_name in ("data", "timestamps"):
                if field_name not in time_series.fields:  # timestamps is optional
                    continue

                candidate_dataset = getattr(time_series, field_name)
                if _is_value_already_written_to_file(
                    candidate_dataset=candidate_dataset, backend_type=backend_type, existing_file=existing_file
                ):
                    continue  # skip

                # Edge case of in-memory ImageSeries with external mode; data is in fields and is empty array
                if isinstance(candidate_dataset, np.ndarray) and not candidate_dataset:
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=time_series, field_name=field_name)
        elif isinstance(neurodata_object, DynamicTable):
            dynamic_table = neurodata_object  # for readability

            for column_name in dynamic_table.colnames:
                candidate_dataset = dynamic_table[column_name].data  # VectorData object
                if _is_value_already_written_to_file(
                    candidate_dataset=candidate_dataset, backend_type=backend_type, existing_file=existing_file
                ):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=dynamic_table[column_name], field_name="data")


def _get_default_configuration(
    nwbfile: NWBFile, backend_type: Literal["hdf5", "zarr"], configurable_dataset: ConfigurableDataset
) -> DatasetConfiguration:
    backend_to_dataset_configuration_class = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
    DatasetConfigurationClass = backend_to_dataset_configuration_class[backend_type]

    neurodata_object = nwbfile.objects[configurable_dataset.object_id]
    field_value = getattr(neurodata_object, configurable_dataset.field)
    iterator = field_value  # Currently restricting to values that are already wrapped in GenericDataChunkIterators
    # TODO: in follow-up, can maybe be wrapped automatically?

    dataset_configuration = DatasetConfigurationClass(
        object_id=configurable_dataset.object_id,
        object_name=configurable_dataset.object_name,
        parent=configurable_dataset.parent,
        field=configurable_dataset.field,
        maxshape=configurable_dataset.maxshape,
        dtype=configurable_dataset.dtype,
        chunk_shape=iterator.chunk_shape,
        buffer_shape=iterator.buffer_shape,
        # Let the compression and/or filters default to the back-end specific values
    )

    return dataset_configuration


def get_default_backend_configuration(
    nwbfile: NWBFile, backend_type: Literal["hdf5", "zarr"]
) -> Union[HDF5BackendConfiguration, ZarrBackendConfiguration]:
    """Fill a default backend configuration to serve as a starting point for further customization."""
    backend_type_to_backend_configuration_classes = dict(hdf5=HDF5BackendConfiguration, zarr=ZarrBackendConfiguration)

    configurable_datasets = get_configurable_datasets(nwbfile=nwbfile)

    dataset_configurations = dict()
    for configurable_dataset in configurable_datasets:
        dataset_configurations.update(
            {
                configurable_dataset: _get_default_configuration(
                    nwbfile=nwbfile, backend_type=backend_type, configurable_dataset=configurable_dataset
                )
            }
        )

    DatasetConfigurationClass = backend_type_to_backend_configuration_classes[backend_type]
    backend_configuration = DatasetConfigurationClass(dataset_configurations=dataset_configurations)

    return backend_configuration
