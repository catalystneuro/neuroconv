from neuroconv.tools.testing import MockEthogramInterface
from neuroconv.tools.testing.data_interface_mixins import EthogramInterfaceTestMixin


class TestMockEthogramInterface(EthogramInterfaceTestMixin):
    data_interface_cls = MockEthogramInterface
    interface_kwargs = dict(num_frames=300, num_behaviors=4, seed=0)
