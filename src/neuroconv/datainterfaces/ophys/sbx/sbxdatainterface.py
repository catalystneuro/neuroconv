from typing import Literal

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    display_name = "Scanbox Imaging"
    associated_suffixes = (".sbx",)
    info = "Interface for Scanbox imaging data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import SbxImagingExtractor

        return SbxImagingExtractor

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        sampling_frequency: float | None = None,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        metadata_key: str | None = None,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .sbx file.
        sampling_frequency : float, optional
        verbose : bool, default: False
        metadata_key : str, optional
            # TODO: improve docstring once #1653 (ophys metadata documentation) is merged
            Metadata key for this interface. When None, defaults to "sbx_imaging".
        """

        if metadata_key is None:
            metadata_key = "sbx_imaging"

        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
            photon_series_type=photon_series_type,
            metadata_key=metadata_key,
        )

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        """
        Get metadata for the Scanbox imaging data.

        Parameters
        ----------
        use_new_metadata_format : bool, default: True
            When False, returns the old list-based metadata format (backward compatible).
            When True, returns dict-based metadata with Scanbox device provenance.

        Returns
        -------
        dict
            Dictionary containing metadata including device information and imaging details
            specific to the Scanbox system.
        """
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            # The registry is keyed by the microscope rather than by this interface: one Scanbox system
            # imaged whatever this session holds, so several interfaces resolve to one device entry.
            device_metadata_key = "scanbox_microscope"
            metadata["Devices"] = {device_metadata_key: {"name": "Microscope", "description": "Scanbox imaging"}}
            metadata["Ophys"] = {
                "ImagingPlanes": {
                    self.metadata_key: {"device_metadata_key": device_metadata_key},
                },
                "MicroscopySeries": {
                    self.metadata_key: {
                        "description": "Imaging data acquired with Scanbox.",
                        "imaging_plane_metadata_key": self.metadata_key,
                    },
                },
            }
            return metadata

        metadata = super().get_metadata(use_new_metadata_format=False)
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
