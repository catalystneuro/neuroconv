"""Collection of helper functions related to configuration of datasets dependent on backend."""

import math

from hdmf.common import Data
from hdmf.data_utils import AbstractDataChunkIterator, DataChunkIterator
from pynwb import NWBContainer, NWBFile, TimeSeries
from pynwb.core import NWBData

from ._configuration_models._base_dataset_io import _find_location_in_memory_nwbfile
from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration
from ..hdmf import _get_nwbfile_builder, has_compound_dtype


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
    nwbfile_is_on_disk = nwbfile.read_io is not None

    # A remapping of the object IDs in the backend configuration might necessary
    locations_to_remap = backend_configuration.find_locations_requiring_remapping(nwbfile=nwbfile)
    if any(locations_to_remap):
        backend_configuration = backend_configuration.build_remapped_backend(locations_to_remap=locations_to_remap)

    builder = _get_nwbfile_builder(nwbfile=nwbfile)

    # `nwbfile.objects` is built on its first read and never invalidated, so it does not hold anything added
    # to the file afterwards. `all_children` recomputes the walk.
    neurodata_objects_by_id = {child.object_id: child for child in nwbfile.all_children()}

    # Set all DataIO based on the configuration
    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.dataset_configurations.values():
        object_id = dataset_configuration.object_id
        dataset_name = dataset_configuration.dataset_name
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        neurodata_object = neurodata_objects_by_id[object_id]
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
            data_chunk_iterator_kwargs = dict(
                buffer_size=math.prod(dataset_configuration.buffer_shape), dtype=dataset_configuration.dtype
            )

        # Table columns
        if isinstance(neurodata_object, Data):
            neurodata_object.set_data_io(
                data_io_class=data_io_class,
                data_io_kwargs=data_io_kwargs,
                data_chunk_iterator_class=data_chunk_iterator_class,
                data_chunk_iterator_kwargs=data_chunk_iterator_kwargs,
            )
            if isinstance(neurodata_object, NWBData):
                # `Data.set_data_io` above assigns to the name-mangled `_Data__data`, but `NWBData` declares its
                # own `__data` attribute and a `data` property reading `_NWBData__data`, which shadows the parent.
                # Without re-syncing the child attribute the DataIO wrapping is silently dropped for every NWBData
                # subclass, the pixel-data Image types among them.
                # TODO: https://github.com/NeurodataWithoutBorders/pynwb/pull/2233 lets the parent own the
                # storage and is merged on pynwb's dev branch, so remove this once the minimum pynwb version
                # is bumped past the release that carries it.
                neurodata_object._NWBData__data = neurodata_object._Data__data
        # Datasets of a TimeSeries or of any other container, including an extension type built from a cached spec
        elif isinstance(neurodata_object, NWBContainer) and not is_dataset_linked:
            neurodata_object.set_data_io(
                dataset_name=dataset_name,
                data_io_class=data_io_class,
                data_io_kwargs=data_io_kwargs,
                data_chunk_iterator_class=data_chunk_iterator_class,
                data_chunk_iterator_kwargs=data_chunk_iterator_kwargs,
            )
        # Skip the setting of a DataIO when target dataset is a link (assume it will be found in parent)
        elif isinstance(neurodata_object, NWBContainer) and is_dataset_linked:
            continue
        # Strictly speaking, it would be odd if a `backend_configuration` got to this line, but might as well be safe
        else:
            raise NotImplementedError(
                f"Unsupported object type {type(neurodata_object)} for backend configuration "
                f"of {neurodata_object.name}!"
            )
