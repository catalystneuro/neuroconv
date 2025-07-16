from neuroconv.tools.testing.data_interface_mixins import (
    PoseEstimationInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface


class TestMockPoseEstimationInterface(PoseEstimationInterfaceTestMixin):
    data_interface_cls = MockPoseEstimationInterface
    interface_kwargs = dict(num_samples=100, num_nodes=3, seed=42)
