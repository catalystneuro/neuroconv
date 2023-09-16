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


_available_zarr_filters = (
    set(zarr.codec_registry.keys())
    - set(
        # These filters do nothing for us, or are things that ought to be implemented at lower HDMF levels
        # or indirectly using HDMF data structures
        (
            "json2",  # no data savings
            "pickle",  # no data savings
            "vlen-utf8",  # enforced by HDMF
            "vlen-array",  # enforced by HDMF
            "vlen-bytes",  # enforced by HDMF
            "adler32",  # checksum
            "crc32",  # checksum
            "fixedscaleoffset",  # enforced indrectly by HDMF/PyNWB data types
            "base64",  # unsure what this would ever be used for
            "n5_wrapper",  # different data format
        )
    )
    - set(  # Forbidding lossy codecs for now, but they could be allowed in the future with warnings
        ("astype", "bitround", "quantize")
    )
)
# TODO: would like to eventually (as separate feature) add an 'auto' method to Zarr
# to harness the wider range of potential methods that are ideal for certain dtypes or structures
# E.g., 'packbits' for boolean (logical) VectorData columns
# | set(("auto",))
AVAILABLE_ZARR_COMPRESSION_METHODS = Literal[tuple(_available_zarr_filters)]


class ZarrDatasetConfiguration(DatasetConfiguration):
    """A data model for configruing options about an object that will become a Zarr Dataset in the file."""

    filter_methods: Union[Tuple[AVAILABLE_ZARR_COMPRESSION_METHODS, ...], None] = None
    filter_options: Union[Tuple[Dict[str, Any]], None] = None
    compression_method: Union[AVAILABLE_ZARR_COMPRESSION_METHODS, bool] = "gzip"  # TODO: would like this to be 'auto'
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings but no annotation typing
    compression_options: Union[Dict[str, Any], None] = None

    @root_validator()
    def validate_filter_methods_and_options_match(cls, values: Dict[str, Any]):
        filter_methods = values["filter_methods"]
        filter_options = values["filter_options"]

        if filter_methods is None and filter_options is not None:
            raise ValueError(f"`filter_methods` is `None` but `filter_options` is not ({filter_options})!")
        elif filter_methods is None and filter_options is None:
            return values

        len_filter_methods = len(filter_methods)
        len_filter_options = len(filter_options)
        if len_filter_methods != len_filter_options:
            raise ValueError(
                f"Length mismatch between `filter_methods` ({len_filter_methods} methods specified) and "
                f"`filter_options` ({len_filter_options} options found)! These two must match one-to-one."
            )

        return values

    # think about extra validation that msgpack2 compression only ideal for datasets of vlen strings

    def get_data_io_keyword_arguments(self) -> Dict[str, Any]:
        filters = None
        if self.filter_methods is not None:
            filters = [
                zarr.codec_registry[filter_method](**filter_options)
                for filter_method, filter_options in zip(self.filter_methods, self.filter_options)
            ]

        if isinstance(self.compression_method, bool):
            compressor = self.compression_method
        else:
            compressor = zarr.codec_registry[self.compression_method](**self.compression_options)

        return dict(chunks=self.chunk_shape, filters=filters, compressor=compressor)


BACKEND_TO_DATASET_CONFIGURATION = dict(hdf5=HDF5DatasetConfiguration, zarr=ZarrDatasetConfiguration)
