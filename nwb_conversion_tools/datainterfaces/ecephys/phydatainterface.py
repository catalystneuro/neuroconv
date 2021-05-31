"""Authors: Cody Baker."""
import spikeextractors as se

from .basesortingextractorinterface import BaseSortingExtractorInterface


class PhySortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a PhySortingExtractor."""

    SX = se.PhySortingExtractor
