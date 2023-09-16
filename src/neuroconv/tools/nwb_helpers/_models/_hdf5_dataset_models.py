"""Collection of helper functions related to configuration of datasets dependent on backend."""
from typing import Any, Dict, Literal, Tuple, Type, Union

import h5py
import psutil
import zarr
from hdmf.backends.hdf5 import H5DataIO
from hdmf.container import DataIO
from hdmf_zarr import ZarrDataIO
from nwbinspector.utils import is_module_installed
from pydantic import BaseModel, Field, root_validator


_base_hdf5_filters = set(h5py.filters.decode) - set(
    (
        "shuffle",  # controlled via H5DataIO
        "fletcher32",  # controlled via H5DataIO
        "scaleoffset",  # enforced indrectly by HDMF/PyNWB data types
    )
)
_available_hdf5_filters = set(_base_hdf5_filters)
if is_module_installed(module_name="hdf5plugin"):
    import hdf5plugin

    _available_hdf5_filters = _available_hdf5_filters | set(
        (str(hdf5plugin_filter).rstrip("'>").split(".")[-1] for hdf5plugin_filter in hdf5plugin.get_filters())
    )  # Manual string parsing because of slight mismatches between .filter_name and actual import class
AVAILABLE_HDF5_COMPRESSION_METHODS = Literal[tuple(_available_hdf5_filters)]


class HDF5Compression(BaseModel):
    method: str
    options: dict


class HDF5DatasetConfiguration(DatasetConfiguration):
    """A data model for configruing options about an object that will become a HDF5 Dataset in the file."""

    compression_method: Union[AVAILABLE_HDF5_COMPRESSION_METHODS, bool] = "gzip"
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Union[Dict[str, Any], None] = None

    def get_data_io_keyword_arguments(self) -> Dict[str, Any]:
        # H5DataIO expects compression/compression_opts in very particular way
        # Easiest way to ensure that is to instantiate hdf5plugin and pass dynamic kwargs
        if is_module_installed(module_name="hdf5plugin"):
            import hdf5plugin

            if self.compression_method in _base_hdf5_filters:
                compression_bundle = dict(
                    compression=self.compression_method, compression_opts=self.compression_options
                )
            else:
                compression_options = self.compression_options or dict()
                compression_bundle = dict(
                    **getattr(hdf5plugin, self.compression_method)(**compression_options),
                    allow_plugin_filters=True,
                )
        else:
            compression_bundle = dict(compression=self.compression_method, compression_opts=self.compression_options)

        return dict(chunks=self.chunk_shape, **compression_bundle)
