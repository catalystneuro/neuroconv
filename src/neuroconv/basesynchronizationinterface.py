"""Abstract class defining the structure of all Extractor-based Interfaces."""
from typing import Optional

from .baseextractorinterface import BaseExtractorInterface
from .tools import get_package


class BaseSynchronizationInterface(BaseExtractorInterface):
    """
    Abstract class defining the structure of all SynchronizationInterfaces.

    A SynchronizationInterface is one that harnesses an extractor class from SpikeInterface to read an analog sync
    pulse from a specific set of channels that map one-to-one onto various interfaces being combined into an
    NWBConverter object.
    """

    def set_channel_to_interface_mapping(self, mapping: dict):
        """
        E.g., mapping = dict(
            TrialsInterface=0,
            VideoInterface=1,
            EyeTrackingInterface=2,
        )
        """
