"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Union

from pynwb import NWBFile

from ._configuration_models._hdf5_backend import HDF5BackendConfiguration
from ._configuration_models._zarr_backend import ZarrBackendConfiguration


def configure_backend(
    nwbfile: NWBFile, backend_configuration: Union[HDF5BackendConfiguration, ZarrBackendConfiguration]
) -> None:
    """Configure all datasets specified in the `backend_configuration` with their appropriate DataIO and options."""
    nwbfile_objects = nwbfile.objects

    data_io_class = backend_configuration.data_io_class
    for dataset_configuration in backend_configuration.dataset_configurations.values():
        object_id = dataset_configuration.dataset_info.object_id
        dataset_name = dataset_configuration.dataset_info.dataset_name
        data_io_kwargs = dataset_configuration.get_data_io_kwargs()

        # TODO: update buffer shape in iterator, if present

        nwbfile_objects[object_id].set_data_io(dataset_name=dataset_name, data_io_class=data_io_class, **data_io_kwargs)
