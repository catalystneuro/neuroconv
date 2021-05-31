from roiextractors import SbxImagingExtractor, Hdf5ImagingExtractor, TiffImagingExtractor

from .baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TIffImagingExtractor"""

    IX = TiffImagingExtractor


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor"""

    IX = Hdf5ImagingExtractor


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor"""

    IX = SbxImagingExtractor
