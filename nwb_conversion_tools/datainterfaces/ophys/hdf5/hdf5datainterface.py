from roiextractors import Hdf5ImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils.json_schema import FilePathType, FloatType, ArrayType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor."""

    IX = Hdf5ImagingExtractor

    def __init__(
        self,
        file_path: FilePathType,
        mov_field: str = "mov",
        sampling_frequency: FloatType = None,
        start_time: FloatType = None,
        metadata: dict = None,
        channel_names: ArrayType = None,
    ):
        super().__init__(
            file_path=file_path,
            mov_field=mov_field,
            sampling_frequency=sampling_frequency,
            start_time=start_time,
            metadata=metadata,
            channel_names=channel_names,
        )
