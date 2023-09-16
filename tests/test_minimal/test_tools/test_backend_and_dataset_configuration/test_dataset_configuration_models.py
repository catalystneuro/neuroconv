"""Unit tests for `get_default_dataset_configurations`."""
import numcodecs
import numpy as np
from hdmf.data_utils import DataChunkIterator
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    configure_backend,
    get_default_backend_configuration,
)
