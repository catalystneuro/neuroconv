from typing import Literal

from ....utils import FilePathType
from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files."""

    display_name = "TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multi-page TIFF files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        sampling_frequency: float,
        verbose: bool = True,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
    ):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_path : FilePathType
        sampling_frequency : float
        verbose : bool, default: True
        photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, default: "TwoPhotonSeries"
        """
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
