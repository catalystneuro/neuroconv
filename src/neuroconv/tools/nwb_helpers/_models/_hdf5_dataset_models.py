"""Base Pydantic models for the HDF5DatasetConfiguration."""
from typing import Any, Dict, Literal, Union

import h5py
from nwbinspector.utils import is_module_installed
from pydantic import Field

from ._base_dataset_models import DatasetConfiguration

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
if is_module_installed(module_name="hdf5plugin"):
    import hdf5plugin

    AVAILABLE_HDF5_COMPRESSION_METHODS.update(
        {
            str(hdf5plugin_filter).rstrip("'>").split(".")[-1]: hdf5plugin_filter
            for hdf5plugin_filter in hdf5plugin.get_filters()
        }
    )


class HDF5DatasetConfiguration(DatasetConfiguration):
    """A data model for configuring options about an object that will become a HDF5 Dataset in the file."""

    # TODO: When using Pydantic v2, replace with `model_config = ConfigDict(...)`
    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

    compression_method: Union[
        Literal[tuple(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())], h5py._hl.filters.FilterRefBase, None
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
        if is_module_installed(module_name="hdf5plugin"):
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
            compression_bundle = dict(compression=self.compression_method, compression_opts=self.compression_options)

        return dict(chunks=self.chunk_shape, **compression_bundle)
