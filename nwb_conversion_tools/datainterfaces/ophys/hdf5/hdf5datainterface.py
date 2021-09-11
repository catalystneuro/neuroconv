from roiextractors import Hdf5ImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor"""

    IX = Hdf5ImagingExtractor
