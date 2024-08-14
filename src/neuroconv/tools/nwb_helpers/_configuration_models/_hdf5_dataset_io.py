"""Base Pydantic models for the HDF5DatasetConfiguration."""

from typing import Any, Dict, Literal, Union

import h5py
from hdmf import Container
from pydantic import Field, InstanceOf
from typing_extensions import Self

from ._base_dataset_io import DatasetIOConfiguration, _find_location_in_memory_nwbfile
from ...importing import is_package_installed

_base_hdf5_filters = set(h5py.filters.decode)
_excluded_hdf5_filters = set(
    (
        "shuffle",  # controlled via H5DataIO
        "fletcher32",  # controlled via H5DataIO
        "scaleoffset",  # enforced indrectly by HDMF/PyNWB data types
    )
)
_available_hdf5_filters = set(_base_hdf5_filters - _excluded_hdf5_filters)
AVAILABLE_HDF5_COMPRESSION_METHODS = {filter_name: filter_name for filter_name in _available_hdf5_filters}
if is_package_installed(package_name="hdf5plugin"):
    import hdf5plugin

    AVAILABLE_HDF5_COMPRESSION_METHODS.update(
        {
            str(hdf5plugin_filter).rstrip("'>").split(".")[-1]: hdf5plugin_filter
            for hdf5plugin_filter in hdf5plugin.get_filters()
        }
    )


class HDF5DatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a HDF5 Dataset in the file."""

    compression_method: Union[
        Literal[tuple(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())], InstanceOf[h5py._hl.filters.FilterRefBase], None
    ] = Field(
        default="gzip",
        description=(
            "The specified compression method to apply to this dataset. "
            "Can be either a string that matches an available method on your system, "
            "or an instantiated h5py/hdf5plugin object."
            "Set to `None` to disable compression."
        ),
    )
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now.
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings - no annotation typing.
    compression_options: Union[Dict[str, Any], None] = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )

    def get_data_io_kwargs(self) -> Dict[str, Any]:
        if is_package_installed(package_name="hdf5plugin"):
            import hdf5plugin

            if self.compression_method in _base_hdf5_filters:
                # Base filters only take particular form of a single input; single int for GZIP; 2-tuple for SZIP
                compression_opts = None
                if self.compression_options is not None:
                    compression_opts = list(self.compression_options.values())[0]
                compression_bundle = dict(compression=self.compression_method, compression_opts=compression_opts)
            elif isinstance(self.compression_method, str):
                compression_options = self.compression_options or dict()
                # The easiest way to ensure the form is correct is to instantiate the hdf5plugin and pass dynamic kwargs
                compression_bundle = dict(
                    **getattr(hdf5plugin, self.compression_method)(**compression_options),
                    allow_plugin_filters=True,
                )
            elif isinstance(self.compression_method, h5py._hl.filters.FilterRefBase):
                compression_bundle = dict(**self.compression_method, allow_plugin_filters=True)
            elif self.compression_method is None:
                compression_bundle = dict(compression=False)
        else:
            # Base filters only take particular form of a single input; single int for GZIP; 2-tuple for SZIP
            compression_opts = None
            if self.compression_options is not None:
                compression_opts = list(self.compression_options.values())[0]
            compression_bundle = dict(compression=self.compression_method, compression_opts=compression_opts)

        return dict(chunks=self.chunk_shape, **compression_bundle)

    @classmethod
    def from_neurodata_object(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
        mode: Literal["default", "existing"] = "default",
    ) -> Self:
        if mode == "default":
            return super().from_neurodata_object(neurodata_object=neurodata_object, dataset_name=dataset_name)
        elif mode == "existing":
            location_in_file = _find_location_in_memory_nwbfile(
                neurodata_object=neurodata_object, field_name=dataset_name
            )
            full_shape = getattr(neurodata_object, dataset_name).shape
            dtype = getattr(neurodata_object, dataset_name).dtype
            chunk_shape = getattr(neurodata_object, dataset_name).chunks
            buffer_shape = getattr(neurodata_object, dataset_name).maxshape
            compression_method = getattr(neurodata_object, dataset_name).compression
            compression_opts = getattr(neurodata_object, dataset_name).compression_opts
            compression_options = dict(compression_opts=compression_opts)
            return cls(
                object_id=neurodata_object.object_id,
                object_name=neurodata_object.name,
                location_in_file=location_in_file,
                dataset_name=dataset_name,
                full_shape=full_shape,
                dtype=dtype,
                chunk_shape=chunk_shape,
                buffer_shape=buffer_shape,
                compression_method=compression_method,
                compression_options=compression_options,
            )
        else:
            raise ValueError(f"mode must be either 'default' or 'existing' but got {mode}")
