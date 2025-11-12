"""Collection of helper functions related to configuration of datasets dependent on backend."""

import importlib
import math

from hdmf.common import Data
from hdmf.data_utils import AbstractDataChunkIterator, DataChunkIterator
from packaging import version
from pynwb import NWBFile, TimeSeries, get_manager

from ._configuration_models._base_dataset_io import _find_location_in_memory_nwbfile
from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration
from ..hdmf import has_compound_dtype
from ..importing import get_package_version, is_package_installed


def configure_backend(
    nwbfile: NWBFile, backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration
) -> None:
    """
    Configure all datasets specified in the `backend_configuration` with their appropriate DataIO and options.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The in-memory pynwb.NWBFile object to configure.
    backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration
        The configuration model to use when configuring the datasets for this backend.
    """
    is_ndx_events_installed = is_package_installed(package_name="ndx_events")
    ndx_events = importlib.import_module("ndx_events") if is_ndx_events_installed else None

    nwbfile_is_on_disk = nwbfile.read_io is not None

    # A remapping of the object IDs in the backend configuration might necessary
    locations_to_remap = backend_configuration.find_locations_requiring_remapping(nwbfile=nwbfile)
    if any(locations_to_remap):
        backend_configuration = backend_configuration.build_remapped_backend(locations_to_remap=locations_to_remap)

    manager = get_manager()
    builder = manager.build(nwbfile, export=True)

    # Set all DataIO based on the configuration
    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.dataset_configurations.values():
        object_id = dataset_configuration.object_id
        dataset_name = dataset_configuration.dataset_name
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        neurodata_object = nwbfile.objects[object_id]
        is_dataset_linked = isinstance(neurodata_object.fields.get(dataset_name), TimeSeries)
        location_in_file = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name=dataset_name)
        dtype_is_compound = has_compound_dtype(builder=builder, location_in_file=location_in_file)
        if (
            isinstance(neurodata_object.fields.get(dataset_name), AbstractDataChunkIterator)
            or dtype_is_compound
            or not nwbfile_is_on_disk
        ):
            data_chunk_iterator_class = None
            data_chunk_iterator_kwargs = dict()
        else:  # If the dataset has been written to disk and it is not compound and it is not already an iterator,
            # we wrap each neurodata_object in a DataChunkIterator in order to support changes to the I/O settings.
            # For more detail, see https://github.com/hdmf-dev/hdmf/issues/1170.
            data_chunk_iterator_class = DataChunkIterator
            data_chunk_iterator_kwargs = dict(buffer_size=math.prod(dataset_configuration.buffer_shape))

        # Table columns
        if isinstance(neurodata_object, Data):
            neurodata_object.set_data_io(
                data_io_class=data_io_class,
                data_io_kwargs=data_io_kwargs,
                data_chunk_iterator_class=data_chunk_iterator_class,
                data_chunk_iterator_kwargs=data_chunk_iterator_kwargs,
            )
        # TimeSeries data or timestamps
        elif isinstance(neurodata_object, TimeSeries) and not is_dataset_linked:
            neurodata_object.set_data_io(
                dataset_name=dataset_name,
                data_io_class=data_io_class,
                data_io_kwargs=data_io_kwargs,
                data_chunk_iterator_class=data_chunk_iterator_class,
                data_chunk_iterator_kwargs=data_chunk_iterator_kwargs,
            )
        # Special ndx-events v0.2.0 types
        elif is_ndx_events_installed and (get_package_version("ndx-events") <= version.parse("0.2.1")):
            # Temporarily skipping LabeledEvents
            if isinstance(neurodata_object, ndx_events.LabeledEvents):
                continue
            elif isinstance(neurodata_object, ndx_events.Events):
                neurodata_object.set_data_io(
                    dataset_name=dataset_name,
                    data_io_class=data_io_class,
                    data_io_kwargs=data_io_kwargs,
                    data_chunk_iterator_class=data_chunk_iterator_class,
                    data_chunk_iterator_kwargs=data_chunk_iterator_kwargs,
                )
        # Skip the setting of a DataIO when target dataset is a link (assume it will be found in parent)
        elif isinstance(neurodata_object, TimeSeries) and is_dataset_linked:
            continue
        # Strictly speaking, it would be odd if a `backend_configuration` got to this line, but might as well be safe
        else:
            raise NotImplementedError(
                f"Unsupported object type {type(neurodata_object)} for backend configuration "
                f"of {neurodata_object.name}!"
            )
