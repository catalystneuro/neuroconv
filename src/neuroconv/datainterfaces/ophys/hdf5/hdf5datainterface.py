from typing import List, Optional

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Hdf5ImagingExtractor."""

    def __init__(
        self,
        file_path: FilePathType,
        mov_field: str = "mov",
        sampling_frequency: Optional[float] = None,
        start_time: Optional[float] = None,
        metadata: Optional[dict] = None,
        channel_names: List[str] = None,
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
