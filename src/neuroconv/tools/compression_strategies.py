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
            self.allow_plugin_filters = True
            hdf5plugin = get_package("hdf5plugin")
            available_plugins = hdf5plugin.get_filters()
            self.plugin = next(filter(lambda x: x.filter_name == self.method_name, available_plugins))
            self.plugin_instance = self.plugin(**self.compression_options)
            self.compression_kwargs = dict(self.plugin_instance)

        else:
            compression = self.method_name
            compression_opts = self.compression_options
            self.compression_kwargs = dict(compression=compression, compression_opts=compression_opts)

    def wrap_data_for_compression(self, data, h5dataio_kwargs: dict = None) -> H5DataIO:

        # In case some other parmaeters of H5DataIO are needed in the future
        h5dataio_kwargs = h5dataio_kwargs or dict()

        h5dataio_kwargs.update(data=data, allow_plugin_filters=self.allow_plugin_filters, **self.compression_kwargs)

        return H5DataIO(**h5dataio_kwargs)


# Another option is to make a class for each compression method but this seems to much
