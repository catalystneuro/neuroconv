"""Collection of helper functions related to configuration of datasets dependent on backend."""

import sys
from typing import Union

from hdmf.common import Data
from pynwb import NWBFile, TimeSeries

from ._configuration_models._base_backend import BackendConfiguration
from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration
from ..importing import is_package_installed


def _remap_backend_configuration_to_nwbfile(
    nwbfile: NWBFile, backend_configuration: Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
) -> BackendConfiguration:
    """
    Remap an existing backend configuration to a new NWBFile.

    If a backend configuration was created with a different NWBFile instance, then
    the neurodata objects ids in the configuration might not match the new NWBFile.

    Use this function to remap the configuration to the new NWBFile using the location in file attribute.

    The function returns a new backend configuration instance that is aligned with the provided `nwbfile`
    without modifying the original `backend_configuration`.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The target NWBFile object to which the configuration will be remapped.
    backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration
        The existing backend configuration to be remapped.

    Returns
    -------
    BackendConfiguration
        A new backend configuration instance that is aligned with the provided `nwbfile`.

    Raises
    ------
    ValueError
        If a dataset from the original configuration cannot be found in the new NWBFile.

    Notes
    -----
    * This function returns a new copy, it does not modify the input `nwbfile` or the original
    `backend_configuration`.
    * If the `nwbfile` and the `backend_configuration` are already aligned (i.e., same identifier
    and all dataset IDs match), the original `backend_configuration` is returned unchanged.
    * Remapping is based on the `location_in_file` attribute of dataset configurations.

    """
    # TODO: Might not be necessary if https://github.com/hdmf-dev/hdmf/issues/1108 is implemented

    # First check if update is necessary
    comes_from_same_nwbfile = nwbfile.identifier == backend_configuration.nwbfile_identifier
    ids_in_backend_configuration = [
        dataset_configuration.object_id
        for dataset_configuration in backend_configuration.dataset_configurations.values()
    ]

    ids_in_nwbfile = nwbfile.objects.keys()
    all_ids_in_backend_configuration_are_in_nwbfile = all(
        dataset_id in ids_in_nwbfile for dataset_id in ids_in_backend_configuration
    )

    if comes_from_same_nwbfile and all_ids_in_backend_configuration_are_in_nwbfile:
        return backend_configuration

    # Create a mapping from location to configuration
    location_to_configuration = {
        dataset_configuration.location_in_file: dataset_configuration
        for dataset_configuration in backend_configuration.dataset_configurations.values()
    }

    # Create a new backend configuration from the NWBFile
    backend_configuration_class = type(backend_configuration)
    remaped_backend_configuration = backend_configuration_class.from_nwbfile(nwbfile=nwbfile)

    # Remap the configurations using the location in file
    for dataset_configuration in remaped_backend_configuration.dataset_configurations.values():
        location_in_file = dataset_configuration.location_in_file
        if location_in_file in location_to_configuration:
            corresponding_configuration = location_to_configuration[location_in_file]
            remaped_backend_configuration.dataset_configurations[location_in_file] = corresponding_configuration
        else:
            raise ValueError(
                f"Could not remap backend configuration created with nwbfile with identifier {backend_configuration.nwbfile_identifier} "
                f"to NWBFile with identifier {nwbfile.identifier}."
                f"Failed to find a configuration for dataset at location {location_in_file} in the backend configuration."
            )

    return remaped_backend_configuration


def configure_backend(
    nwbfile: NWBFile, backend_configuration: Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
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
    ndx_events = sys.modules.get("ndx_events", None)

    # A remapping of the object IDs in the backend configuration might necessary if
    # The backend configuration was created with a different NWBFile instance
    if nwbfile.identifier != backend_configuration.nwbfile_identifier:
        backend_configuration = _remap_backend_configuration_to_nwbfile(
            nwbfile=nwbfile, backend_configuration=backend_configuration
        )

    # Set all DataIO based on the configuration
    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.dataset_configurations.values():
        object_id = dataset_configuration.object_id
        dataset_name = dataset_configuration.dataset_name
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        neurodata_object = nwbfile.objects[object_id]
        is_dataset_linked = isinstance(neurodata_object.fields.get(dataset_name), TimeSeries)

        # Table columns
        if isinstance(neurodata_object, Data):
            neurodata_object.set_data_io(data_io_class=data_io_class, data_io_kwargs=data_io_kwargs)
        # TimeSeries data or timestamps
        elif isinstance(neurodata_object, TimeSeries) and not is_dataset_linked:
            neurodata_object.set_data_io(
                dataset_name=dataset_name, data_io_class=data_io_class, data_io_kwargs=data_io_kwargs
            )
        # Special ndx-events v0.2.0 types
        elif is_ndx_events_installed and isinstance(neurodata_object, ndx_events.Events):
            neurodata_object.set_data_io(
                dataset_name=dataset_name, data_io_class=data_io_class, data_io_kwargs=data_io_kwargs
            )
        # But temporarily skipping LabeledEvents
        elif is_ndx_events_installed and isinstance(neurodata_object, ndx_events.LabeledEvents):
            continue
        # Skip the setting of a DataIO when target dataset is a link (assume it will be found in parent)
        elif isinstance(neurodata_object, TimeSeries) and is_dataset_linked:
            continue
        # Strictly speaking, it would be odd if a `backend_configuration` got to this line, but might as well be safe
        else:
            raise NotImplementedError(
                f"Unsupported object type {type(neurodata_object)} for backend configuration "
                f"of {neurodata_object.name}!"
            )
