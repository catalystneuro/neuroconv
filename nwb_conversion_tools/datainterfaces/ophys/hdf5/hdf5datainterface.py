from roiextractors import SbxImagingExtractor, Hdf5ImagingExtractor, TiffImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor"""

    IX = Hdf5ImagingExtractor
