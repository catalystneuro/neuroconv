from typing import Literal
from datetime import datetime

from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Inscopix Imaging Extractor."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix imaging data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : str
            Path to the .isxd Inscopix file.
        verbose : bool, optional
            If True, outputs additional information during processing.
        """
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            photon_series_type="OnePhotonSeries", 
        )

    def get_metadata(self) -> DeepDict:
        """
        Retrieve the metadata for the Inscopix imaging data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            photon series configuration, and Inscopix-specific acquisition parameters.
        """
        metadata = super().get_metadata()
        extractor = self.imaging_extractor

        # Get timing information (only session start time if present)
        timing = extractor.get_timing()
        if timing and hasattr(timing, 'start'):
            session_start_time = timing.start
            if hasattr(session_start_time, 'to_datetime'):
                session_start_time = session_start_time.to_datetime()
            elif not isinstance(session_start_time, datetime):
                session_start_time = datetime.fromisoformat(str(session_start_time).replace('Z', '+00:00'))
            metadata["NWBFile"]["session_start_time"] = session_start_time.isoformat()
    
        # Get acquisition information 
        acquisition_info = extractor.get_acquisition_info()
        if acquisition_info:
            device_metadata = metadata["Ophys"]["Device"][0]
            microscope_info = []
            if "Microscope Type" in acquisition_info:
                microscope_info.append(f"Type: {acquisition_info['Microscope Type']}")
            if "Microscope Serial Number" in acquisition_info:
                microscope_info.append(f"Serial: {acquisition_info['Microscope Serial Number']}")
            if "Acquisition SW Version" in acquisition_info:
                microscope_info.append(f"Software: {acquisition_info['Acquisition SW Version']}")
            if microscope_info:
                device_metadata["description"] = f"Inscopix Microscope ({', '.join(microscope_info)})"

            imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
            acquisition_details = []
            if "Exposure Time (ms)" in acquisition_info:
                acquisition_details.append(f"Exposure Time (ms): {acquisition_info['Exposure Time (ms)']}")
            if "Microscope Gain" in acquisition_info:
                acquisition_details.append(f"Gain: {acquisition_info['Microscope Gain']}")
            if "Microscope Focus" in acquisition_info:
                acquisition_details.append(f"Focus: {acquisition_info['Microscope Focus']}")
            if "efocus" in acquisition_info:
                acquisition_details.append(f"eFocus: {acquisition_info['efocus']}")
            if "Microscope EX LED Power (mw/mm^2)" in acquisition_info:
                acquisition_details.append(f"EX LED Power (mw/mm^2): {acquisition_info['Microscope EX LED Power (mw/mm^2)']}")
            if "Microscope OG LED Power (mw/mm^2)" in acquisition_info:
                acquisition_details.append(f"OG LED Power (mw/mm^2): {acquisition_info['Microscope OG LED Power (mw/mm^2)']}")

            if acquisition_details:
                current_description = imaging_plane_metadata.get("description", "Inscopix Imaging Plane")
                imaging_plane_metadata["description"] = f"{current_description} ({'; '.join(acquisition_details)})"
            
            # session and subject information
            if "Session Name" in acquisition_info and acquisition_info["Session Name"]:
                metadata["NWBFile"]["session_id"] = acquisition_info["Session Name"]
            if "Experimenter Name" in acquisition_info and acquisition_info["Experimenter Name"]:
                metadata["NWBFile"]["experimenter"] = [acquisition_info["Experimenter Name"]]

            # Subject information
            species = acquisition_info.get("Animal Species", "")
            if not species:
                species = "Unknown species"  # or another appropriate default
            subject_info = {
                "subject_id": acquisition_info.get("Animal ID", ""),
                "sex": acquisition_info.get("Animal Sex", "").upper(),
                "species": species,
            }
            if "Animal Description" in acquisition_info and acquisition_info["Animal Description"]:
                subject_info["description"] = acquisition_info["Animal Description"]
            if "Animal Weight" in acquisition_info and acquisition_info["Animal Weight"]:
                subject_info["weight"] = str(acquisition_info["Animal Weight"])
            if "Animal Date of Birth" in acquisition_info and acquisition_info["Animal Date of Birth"]:
                subject_info["date_of_birth"] = acquisition_info["Animal Date of Birth"]

            if "Subject" in metadata and isinstance(metadata["Subject"], dict):
                metadata["Subject"].update(subject_info)
            else:
                metadata["Subject"] = subject_info
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "OnePhotonSeries",  # Default is OnePhoton
    ):
        """
        Add the Inscopix data to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            NWB file to add the data to.
        metadata : dict, optional
            Metadata dictionary.
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, optional
            Specifies the type of photon series to be used. Defaults to "OnePhotonSeries"
            for Inscopix data.
        """
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
        )