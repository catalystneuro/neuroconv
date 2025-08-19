from dateutil.parser import parse
from pydantic import DirectoryPath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....tools.ophys_metadata_conversion import (
    is_old_ophys_metadata_format,
    update_old_ophys_metadata_format_to_new,
)
from ....utils import DeepDict


class MicroManagerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MicroManagerTiffImagingExtractor."""

    display_name = "Micro-Manager TIFF Imaging"
    associated_suffixes = (".ome", ".tif", ".json")
    info = "Interface for Micro-Manager TIFF imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Micro-Manager TIFF imaging interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the Micro-Manager TIFF interface.
        """
        source_schema = super().get_source_schema()

        source_schema["properties"]["folder_path"]["description"] = "The folder containing the OME-TIF image files."
        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False, metadata_key: str = "default"):
        """
        Data Interface for MicroManagerTiffImagingExtractor.

        Parameters
        ----------
        folder_path : DirectoryPath
            The folder path that contains the OME-TIF image files (.ome.tif files) and
           the 'DisplaySettings' JSON file.
        verbose : bool, default: False
            Whether to print verbose output.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for Device, ImagingPlane, and TwoPhotonSeries.
            Default is "default".
        """
        super().__init__(folder_path=folder_path, metadata_key=metadata_key)
        self.verbose = verbose
        # Micro-Manager uses "Default" as channel name, for clarity we rename it to  'OpticalChannelDefault'
        channel_name = self.imaging_extractor._channel_names[0]
        self.imaging_extractor._channel_names = [f"OpticalChannel{channel_name}"]

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Micro-Manager TIFF imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time, imaging plane details,
            and two-photon series configuration.
        """
        metadata = super().get_metadata()

        # Handle backward compatibility
        if is_old_ophys_metadata_format(metadata):
            metadata = update_old_ophys_metadata_format_to_new(metadata)

        micromanager_metadata = self.imaging_extractor.micromanager_metadata
        session_start_time = parse(micromanager_metadata["Summary"]["StartTime"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        # Update imaging plane metadata
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlanes"][self.metadata_key]
        imaging_plane_metadata.update(
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        # Update two photon series metadata
        metadata["Ophys"]["TwoPhotonSeries"][self.metadata_key].update(
            unit="px",
            format="tiff",
        )

        return metadata
