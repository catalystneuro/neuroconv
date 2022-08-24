from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType, FloatType, ArrayType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor."""

    def __init__(
        self,
        file_path: FilePathType,
        mov_field: str = "mov",
        sampling_frequency: FloatType = None,
        start_time: FloatType = None,
        metadata: dict = None,
        channel_names: ArrayType = None,
        verbose: bool = True,
    ):
        super().__init__(
            file_path=file_path,
            mov_field=mov_field,
            sampling_frequency=sampling_frequency,
            start_time=start_time,
            metadata=metadata,
            channel_names=channel_names,
            verbose=verbose,
        )
