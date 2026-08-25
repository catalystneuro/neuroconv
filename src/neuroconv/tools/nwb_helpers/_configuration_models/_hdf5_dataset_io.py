"""Base Pydantic models for the HDF5DatasetConfiguration."""

from typing import Any, Literal

import h5py
from hdmf import Container
from pydantic import Field, InstanceOf
from typing_extensions import Self

from ._base_dataset_io import DatasetIOConfiguration
from ...importing import is_package_installed

_base_hdf5_filters = set(h5py.filters.decode)
_excluded_hdf5_filters = set(
    (
        "shuffle",  # controlled via H5DataIO
        "fletcher32",  # controlled via H5DataIO
        "scaleoffset",  # enforced indirectly by HDMF/PyNWB data types
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


def _compression_opts_from(compression_options: dict[str, Any] | None) -> int | tuple | None:
    """
    Reduce the options of a base HDF5 filter to the single value `h5py` takes as `compression_opts`.

    A base filter takes one value rather than keywords: an int for gzip, a 2-tuple for szip. The name
    it is stated under varies, `level` from a caller and `compression_opts` from a configuration read
    back off disk, so the value is taken by position. Two of them cannot both be passed, and silently
    dropping one is worse than saying so.
    """
    if not compression_options:
        return None
    if len(compression_options) > 1:
        raise ValueError(
            f"A base HDF5 filter takes a single option, but {len(compression_options)} were given "
            f"({sorted(compression_options)}). Name only the one `h5py` calls `compression_opts`."
        )
    return next(iter(compression_options.values()))


class HDF5DatasetIOConfiguration(DatasetIOConfiguration):
    """A data model for configuring options about an object that will become a HDF5 Dataset in the file."""

    compression_method: (
        Literal[
            "szip",
            "lzf",
            "gzip",
            "Bitshuffle",
            "Blosc",
            "Blosc2",
            "BZip2",
            "FciDecomp",
            "LZ4",
            "Sperr",
            "SZ",
            "SZ3",
            "Zfp",
            "Zstd",
        ]
        | InstanceOf[h5py._hl.filters.FilterRefBase]
        | None
    ) = Field(
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
    compression_options: dict[str, Any] | None = Field(
        default=None, description="The optional parameters to use for the specified compression method."
    )

    def get_data_io_kwargs(self) -> dict[str, Any]:
        # Handled before the branch so that disabling compression means the same thing whether or not
        # `hdf5plugin` happens to be installed
        if self.compression_method is None:
            compression_bundle = dict(compression=False)
        elif self.compression_method in _base_hdf5_filters:
            compression_bundle = dict(
                compression=self.compression_method,
                compression_opts=_compression_opts_from(compression_options=self.compression_options),
            )
        elif isinstance(self.compression_method, h5py._hl.filters.FilterRefBase):
            compression_bundle = dict(**self.compression_method, allow_plugin_filters=True)
        else:
            # The easiest way to ensure the form is correct is to instantiate the hdf5plugin and pass dynamic kwargs
            import hdf5plugin

            plugin_class = getattr(hdf5plugin, self.compression_method)
            plugin_instance = plugin_class(**(self.compression_options or dict()))
            compression_bundle = dict(**plugin_instance, allow_plugin_filters=True)

        return dict(chunks=self.chunk_shape, **compression_bundle)

    @classmethod
    def from_neurodata_object_with_existing(
        cls,
        neurodata_object: Container,
        dataset_name: Literal["data", "timestamps"],
    ) -> Self:
        """
        Construct an HDF5DatasetIOConfiguration from existing dataset settings.

        Parameters
        ----------
        neurodata_object : hdmf.Container
            The neurodata object containing the field that has been read from disk.
        dataset_name : "data" or "timestamps"
            The name of the field that corresponds to the dataset on disk.

        Returns
        -------
        Self
            An HDF5DatasetIOConfiguration instance with settings matching the existing dataset.
        """
        kwargs = cls.get_kwargs_from_neurodata_object(
            neurodata_object=neurodata_object,
            dataset_name=dataset_name,
        )
        dataset = cls.get_dataset(neurodata_object=neurodata_object, dataset_name=dataset_name)
        compression_method = dataset.compression
        compression_opts = dataset.compression_opts
        compression_options = dict(compression_opts=compression_opts)
        return cls(
            **kwargs,
            compression_method=compression_method,
            compression_options=compression_options,
        )
