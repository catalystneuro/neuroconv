"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Dict, Iterable, Literal, Union

import h5py
import zarr
from hdmf.data_utils import DataIO, GenericDataChunkIterator
from hdmf.utils import get_data_shape
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.base import DynamicTable

from ._dataset_and_backend_models import (
    BackendConfiguration,
    ConfigurableDataset,
    DatasetConfiguration,
    HDF5BackendConfiguration,
    HDF5DatasetConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetConfiguration,
)


def _get_dataset_metadata(neurodata_object: Union[TimeSeries, DynamicTable], field_name: str) -> ConfigurableDataset:
    """Fill in the Dataset model with as many values as can be automatically detected or inferred."""
    field_value = getattr(neurodata_object, field_name)
    if field_value is not None and not isinstance(field_value, DataIO):
        return ConfigurableDataset(
            object_id=neurodata_object.object_id,
            object_name=neurodata_object.name,
            parent=neurodata_object.get_ancestor().name,
            field=field_name,
            maxshape=get_data_shape(data=field_value),
            # think on cases that don't have a dtype attr
            dtype=str(getattr(field_value, "dtype", "unknown")),
        )


def _value_already_written_to_file(
    value: Union[h5py.Dataset, zarr.Array],
    backend_type: Literal["hdf5", "zarr"],
    existing_file: Union[h5py.File, zarr.Group, None],
) -> bool:
    """
    Determine if the neurodata object is already written to the file on disk.

    This object should then be skipped by the `get_io_datasets` function when working in append mode.
    """
    return (
        isinstance(value, h5py.Dataset)  # If the source data is an HDF5 Dataset
        and backend_type == "hdf5"  # If working in append mode
        and value.file == existing_file  # If the source HDF5 Dataset is the appending NWBFile
    ) or (
        isinstance(value, zarr.Array)  # If the source data is an Zarr Array
        and backend_type == "zarr"  # If working in append mode
        and value.store == existing_file  # If the source Zarr 'file' is the appending NWBFile
    )


def get_configurable_datasets(nwbfile: NWBFile) -> Iterable[ConfigurableDataset]:
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
            for field_name in ("data", "timestamps"):
                if field_name not in neurodata_object.fields:  # timestamps is optional
                    continue

                field_value = getattr(neurodata_object, field_name)
                if _value_already_written_to_file(
                    value=field_value, backend_type=backend_type, existing_file=existing_file
                ):
                    continue  # skip
                # Currently requiring a ConfigurableDataset to apply only to data wrapped in a GenericDataChunkIterator
                # TODO: in follow-up, can maybe be wrapped automatically?
                if not isinstance(field_value, GenericDataChunkIterator):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=neurodata_object, field_name=field_name)
        elif isinstance(neurodata_object, DynamicTable):
            for column_name in getattr(neurodata_object, "colnames"):
                column_value = getattr(neurodata_object, column_name).data
                if _value_already_written_to_file(
                    value=column_value, backend_type=backend_type, existing_file=existing_file
                ):
                    continue  # skip
                # Currently requiring a ConfigurableDataset to apply only to data wrapped in a GenericDataChunkIterator
                # TODO: in follow-up, can maybe be wrapped automatically?
                if not isinstance(column_value, GenericDataChunkIterator):
                    continue  # skip

                yield _get_dataset_metadata(neurodata_object=neurodata_object[column_name], field_name="data")


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


def get_default_backend_configuration(nwbfile: NWBFile, backend_type: Literal["hdf5", "zarr"]) -> BackendConfiguration:
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
    backend_configuration = DatasetConfigurationClass(
        backend_type=backend_type, dataset_configurations=dataset_configurations
    )
    return backend_configuration
