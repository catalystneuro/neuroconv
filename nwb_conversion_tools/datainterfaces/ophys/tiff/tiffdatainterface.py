from roiextractors import SbxImagingExtractor, Hdf5ImagingExtractor, TiffImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TIffImagingExtractor"""

    IX = TiffImagingExtractor
