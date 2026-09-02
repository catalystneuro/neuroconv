"""Base Pydantic models for the HDF5DatasetConfiguration."""

from typing import Any, ClassVar, Literal

import h5py
from hdmf import Container
from pydantic import Field, InstanceOf, model_validator
from typing_extensions import Self

from ._base_dataset_io import DatasetIOConfiguration
from ...importing import is_package_installed

_base_hdf5_filters = set(h5py.filters.decode)
_excluded_hdf5_filters = set(
    (
        "shuffle",  # not a compression method; reachable as an entry of `compressors`
        "fletcher32",  # not a compression method; reachable as an entry of `compressors`
        "scaleoffset",  # H5DataIO does not accept it, so it is unreachable through NWB
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

    # H5DataIO takes these as their own boolean keyword arguments rather than as entries of a codec chain,
    # so they can never be the compression method of a dataset.
    _pure_filter_names: ClassVar[tuple[str, ...]] = ("shuffle", "fletcher32")

    # The compression methods are built from the same dictionary the rest of the library reports as available,
    # rather than spelled out here, so a filter a new hdf5plugin release adds is accepted instead of being
    # announced as available and then rejected by this field.
    compressors: (
        list[
            Literal[(*_pure_filter_names, *AVAILABLE_HDF5_COMPRESSION_METHODS.keys())]
            | InstanceOf[h5py._hl.filters.FilterRefBase]
        ]
        | None
    ) = Field(
        default=["gzip"],
        description=(
            "The ordered collection of codecs to apply to this dataset. Each element can be either a string that "
            "matches an available method on your system, or an instantiated h5py/hdf5plugin object. "
            "'shuffle' and 'fletcher32' are filters rather than compression methods, so they compose with one "
            "rather than replacing it. HDF5 fixes where each sits in the pipeline, so the list must read "
            "['shuffle', <compression method>, 'fletcher32']. "
            "Set to `None` to disable compression."
        ),
    )
    # TODO: actually provide better schematic rendering of options. Only support defaults in GUIDE for now.
    # Looks like they'll have to be hand-typed however... Can try parsing the google docstrings - no annotation typing.
    compressor_options: list[dict[str, Any] | None] | None = Field(
        default=None, description="The optional parameters to use for each specified compressor."
    )

    @model_validator(mode="after")
    def validate_compressor_order(self) -> Self:
        """HDF5 does not let the caller choose where each filter sits in the pipeline, so validate against its order."""
        if self.compressors is None:
            return self

        for filter_name in self._pure_filter_names:
            if sum(compressor == filter_name for compressor in self.compressors) > 1:
                raise ValueError(f"The '{filter_name}' filter can only appear once in `compressors`!")

        compression_methods = [
            compressor
            for compressor in self.compressors
            if not (isinstance(compressor, str) and compressor in self._pure_filter_names)
        ]
        if len(compression_methods) > 1:
            raise ValueError(
                f"HDF5 accepts at most one compression method per dataset, but `compressors` names "
                f"{len(compression_methods)} of them ({compression_methods})!"
            )

        def _position(compressor) -> int:
            if compressor == "shuffle":
                return 0
            if compressor == "fletcher32":
                return 2
            return 1

        positions = [_position(compressor) for compressor in self.compressors]
        if positions != sorted(positions):
            raise ValueError(
                "HDF5 fixes the order of its filter pipeline, so it cannot be chosen: 'shuffle' is always applied "
                "before the compression method and 'fletcher32' always after it. Write `compressors` as "
                f"['shuffle', <compression method>, 'fletcher32'] instead of {self.compressors}!"
            )

        if self.compressor_options is not None and len(self.compressor_options) != len(self.compressors):
            raise ValueError(
                f"Length mismatch between `compressors` ({len(self.compressors)} specified) and "
                "`compressor_options` "
                f"({len(self.compressor_options)} found)! They should be the same length."
            )

        return self

    def get_data_io_kwargs(self) -> dict[str, Any]:
        compressors = self.compressors or []
        compressor_options = self.compressor_options or [None] * len(compressors)

        # 'shuffle' and 'fletcher32' are their own keyword arguments on H5DataIO rather than entries of a chain
        filter_kwargs = {
            compressor: True
            for compressor in compressors
            if isinstance(compressor, str) and compressor in self._pure_filter_names
        }
        compression_index = self._compressor_index()
        compression_method = None if compression_index is None else compressors[compression_index]
        compression_options = None if compression_index is None else compressor_options[compression_index]

        # Handled before the branch so that disabling compression means the same thing whether or not
        # `hdf5plugin` happens to be installed
        if compression_method is None:
            compression_bundle = dict(compression=False)
        elif compression_method in _base_hdf5_filters:
            # A base filter takes one value rather than keywords, an int for gzip and a 2-tuple for szip.
            # The name it arrives under varies, `level` from a caller and `compression_opts` from a
            # configuration read back off disk, so the value is taken by position rather than by name.
            compression_bundle = dict(
                compression=compression_method,
                compression_opts=next(iter((compression_options or dict()).values()), None),
            )
        elif isinstance(compression_method, h5py._hl.filters.FilterRefBase):
            compression_bundle = dict(**compression_method, allow_plugin_filters=True)
        else:
            # The easiest way to ensure the form is correct is to instantiate the hdf5plugin and pass dynamic kwargs
            import hdf5plugin

            plugin_class = getattr(hdf5plugin, compression_method)
            plugin_instance = plugin_class(**(compression_options or dict()))
            compression_bundle = dict(**plugin_instance, allow_plugin_filters=True)

        return dict(chunks=self.chunk_shape, **compression_bundle, **filter_kwargs)

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

        # Rebuild the pipeline in the order HDF5 applies it
        compressors = []
        compressor_options = []
        if dataset.shuffle:
            compressors.append("shuffle")
            compressor_options.append(None)
        if dataset.compression is not None:
            compressors.append(dataset.compression)
            compressor_options.append(dict(compression_opts=dataset.compression_opts))
        if dataset.fletcher32:
            compressors.append("fletcher32")
            compressor_options.append(None)

        return cls(
            **kwargs,
            compressors=compressors or None,
            compressor_options=compressor_options or None,
        )
