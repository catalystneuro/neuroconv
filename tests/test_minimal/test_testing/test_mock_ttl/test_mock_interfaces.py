from pathlib import Path

from pynwb import NWBHDF5IO
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.testing import MockBehaviorEventInterface, MockSpikeGLXNIDQInterface


# TODO
