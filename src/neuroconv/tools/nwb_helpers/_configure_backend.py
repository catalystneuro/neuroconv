"""Collection of helper functions related to configuration of datasets dependent on backend."""

from typing import Union

from hdmf.common import Data
from pynwb import NWBFile, TimeSeries

from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration


def configure_backend(
    nwbfile: NWBFile, backend_configuration: Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
) -> None:
    """Configure all datasets specified in the `backend_configuration` with their appropriate DataIO and options."""
    nwbfile_objects = nwbfile.objects

    # When a configuration is generated on an equivalent NWBFile elsewhere in memory, the object IDs will not match
    # But a mapping can be formed to reconcile the two
    # This is the case for the interface and converter usage of the feature (since they are separate workflow steps)
    # As well as the NWB GUIDE (since they are separate endpoints in the Flask server)
    nwbfile_object_ids = [nwbfile_object_id for nwbfile_object_id in nwbfile_objects.keys()]
    dataset_configuration_object_ids = [
        dataset_configuration.object_id in nwbfile_object_ids
        for dataset_configuration in backend_configuration.dataset_configurations.values()
    ]
    dataset_configuration_to_nwbfile_object_ids = {  # Default to identity
        dataset_configuration_object_id: dataset_configuration_object_id
        for dataset_configuration_object_id in dataset_configuration_object_ids
    }
    if not all(
        dataset_configuration_object_id in nwbfile_object_ids
        for dataset_configuration_object_id in dataset_configuration_object_ids
    ):
        backend_configuration_class = type(backend_configuration)
        new_default_backend_configuration = backend_configuration_class.from_nwbfile(nwbfile=nwbfile)
        locations_in_file_to_new_object_ids = {
            dataset_configuration.location_in_file: dataset_configuration.object_id
            for dataset_configuration in new_default_backend_configuration.dataset_configurations.values()
        }

        dataset_configuration_to_nwbfile_object_ids = {
            dataset_configuration.object_id: locations_in_file_to_new_object_ids[dataset_configuration.location_in_file]
            for dataset_configuration in backend_configuration.dataset_configurations.values()
        }

    # Set all DataIO based on the configuration
    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.dataset_configurations.values():
        object_id = dataset_configuration_to_nwbfile_object_ids[dataset_configuration.object_id]
        dataset_name = dataset_configuration.dataset_name
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        nwbfile_object = nwbfile_objects[object_id]
        is_dataset_linked = isinstance(nwbfile_object.fields.get(dataset_name), TimeSeries)
        # Table columns
        if isinstance(nwbfile_object, Data):
            nwbfile_object.set_data_io(data_io_class=data_io_class, data_io_kwargs=data_io_kwargs)
        # TimeSeries data or timestamps
        elif isinstance(nwbfile_object, TimeSeries) and not is_dataset_linked:
            nwbfile_object.set_data_io(
                dataset_name=dataset_name, data_io_class=data_io_class, data_io_kwargs=data_io_kwargs
            )
        # Skip the setting of a DataIO when target dataset is a link (assume it will be found in parent)
        elif isinstance(nwbfile_object, TimeSeries) and is_dataset_linked:
            continue
        # Strictly speaking, it would be odd if a backend_configuration led to this, but might as well be safe
        else:
            raise NotImplementedError(
                f"Unsupported object type {type(nwbfile_object)} for backend configuration of {nwbfile_object.name}!"
            )
