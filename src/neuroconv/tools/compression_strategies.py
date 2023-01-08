from abc import ABC, abstractmethod

from hdmf.backends.hdf5.h5_utils import H5DataIO

from .importing import get_package

# Instances would be HDF5 or Zarr
class CompressionStategy(ABC):
    @abstractmethod
    def validate_and_format(self):
        pass

    @abstractmethod
    def wrap_data_for_compression(self):
        pass

    # @staticmethod
    # @abstractmethod
    # def available_methods():
    #     pass
    # Maybe? Can be a instance property


# We could also have ZarrCompressionStrategy(CompressionStategy): # for implementing wrapping with ZarrDataIO
class HDF5CompressionStrategy(CompressionStategy):

    dynamic_filters_names = ["blosc", "bshuf", "bzip2", "fcidecomp", "lz4", "sz", "zfp", "zstd"]

    def __init__(self, method_name: str, compression_options: dict = None):
        self.method_name = method_name
        self.compression_options = compression_options
        self.allow_plugin_filters = False

        self.validate_and_format()

    def validate_and_format(self):

        # Dynamic filters
        if self.method_name in self.dynamic_filters_names:
            hdf5plugin = get_package("hdf5plugin")
            available_plugins = hdf5plugin.get_filters()
            self.dynamic_filter = next(filter(lambda x: x.filter_name == self.method_name, available_plugins))
            self.method_name = self.dynamic_filter.filter_id
            self.allow_plugin_filters = True
            if self.compression_options is not None:
                raise ValueError("Compression options propagation is not yet supported for dynamic filters")

        # Zip
        if self.method_name == "gzip":
            if self.compression_options:
                self.compression_options = self.compression_options.get("level", 4)
                assert self.compression_options in range(10)  # This is checked by H5DataIO anyway, just as an example

    def wrap_data_for_compression(self, data, h5dataio_kwargs: dict = None) -> H5DataIO:

        # In case some other parmaeters of H5DataIO are needed in the future
        h5dataio_kwargs = h5dataio_kwargs or dict()

        h5dataio_kwargs.update(
            data=data,
            compression=self.method_name,
            compression_opts=self.compression_options,
            allow_plugin_filters=self.allow_plugin_filters,
        )

        return H5DataIO(**h5dataio_kwargs)


# Another option is to make a class for each compression method but this seems to much
