from roiextractors import SbxImagingExtractor, Hdf5ImagingExtractor, TiffImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor"""

    IX = SbxImagingExtractor
