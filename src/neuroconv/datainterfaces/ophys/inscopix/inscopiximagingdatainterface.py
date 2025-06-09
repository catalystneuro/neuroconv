from pydantic import FilePath, validate_call
from typing import Literal
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
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "OnePhotonSeries",
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the .isxd Inscopix file.
        verbose : bool, optional
            If True, outputs additional information during processing.
        """
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            photon_series_type=photon_series_type,
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

        # Get session information using new extractor methods
        session_info = extractor.get_session_info()

        # Session start time
        session_start_time = extractor.get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Session name and experimenter
        if session_info.get("session_name"):
            metadata["NWBFile"]["session_id"] = session_info["session_name"]
        if session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        # Get device information
        device_info = extractor.get_device_info()
        if device_info:
            device_metadata = metadata["Ophys"]["Device"][0]

            # Update the actual device name
            if device_info.get("device_name"):
                device_metadata["name"] = device_info["device_name"]

            # Build device description
            microscope_info = []
            if device_info.get("device_serial_number"):
                microscope_info.append(f"Serial: {device_info['device_serial_number']}")
            if device_info.get("acquisition_software_version"):
                microscope_info.append(f"Software: {device_info['acquisition_software_version']}")

            if microscope_info:
                device_metadata["description"] = f"Inscopix Microscope ({', '.join(microscope_info)})"

            # Update imaging plane metadata with acquisition details
            imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]

            # Update imaging plane device reference to match the actual device name
            if device_info.get("device_name"):
                imaging_plane_metadata["device"] = device_info["device_name"]

            acquisition_details = []
            if device_info.get("exposure_time_ms"):
                acquisition_details.append(f"Exposure Time (ms): {device_info['exposure_time_ms']}")
            if device_info.get("microscope_gain"):
                acquisition_details.append(f"Gain: {device_info['microscope_gain']}")
            if device_info.get("microscope_focus"):
                acquisition_details.append(f"Focus: {device_info['microscope_focus']}")
            if device_info.get("efocus"):
                acquisition_details.append(f"eFocus: {device_info['efocus']}")
            if device_info.get("led_power_ex_mw_per_mm2"):
                acquisition_details.append(f"EX LED Power (mw/mm^2): {device_info['led_power_ex_mw_per_mm2']}")
            if device_info.get("led_power_og_mw_per_mm2"):
                acquisition_details.append(f"OG LED Power (mw/mm^2): {device_info['led_power_og_mw_per_mm2']}")

            if acquisition_details:
                current_description = imaging_plane_metadata.get(
                    "description", "The plane or volume being imaged by the microscope."
                )
                imaging_plane_metadata["description"] = f"{current_description} ({'; '.join(acquisition_details)})"

        # Subject
        subject_info = extractor.get_subject_info()

        # Build subject metadata
        subject_metadata = {}
        has_any_subject_data = False

        # Subject ID
        if subject_info and subject_info.get("animal_id"):
            subject_metadata["subject_id"] = subject_info["animal_id"]
            has_any_subject_data = True

        species_value = None
        strain_value = None

        if subject_info and subject_info.get("species"):
            species_raw = subject_info["species"]
            # If it contains genotype info or doesn't NWB match format, put it in strain instead
            if " " in species_raw and species_raw[0].isupper() and species_raw.split()[1][0].islower():
                species_value = species_raw
            else:
                strain_value = species_raw

            if species_value:
                subject_metadata["species"] = species_value
                has_any_subject_data = True
            if strain_value:
                subject_metadata["strain"] = strain_value
                has_any_subject_data = True

        # Sex
        sex_mapping = {"m": "M", "male": "M", "f": "F", "female": "F", "u": "U", "unknown": "U"}
        if subject_info and subject_info.get("sex"):
            mapped_sex = sex_mapping.get(subject_info["sex"].lower(), "U")
            subject_metadata["sex"] = mapped_sex
            has_any_subject_data = True

        if subject_info:
            if subject_info.get("description"):
                subject_metadata["description"] = subject_info["description"]
                has_any_subject_data = True
            if subject_info.get("date_of_birth"):
                subject_metadata["date_of_birth"] = subject_info["date_of_birth"]
                has_any_subject_data = True
            if subject_info.get("weight") and subject_info["weight"] > 0:
                subject_metadata["weight"] = str(subject_info["weight"])
                has_any_subject_data = True

        # Add Subject if we have ANY subject information, filling required fields with defaults
        if has_any_subject_data:
            if "subject_id" not in subject_metadata:
                subject_metadata["subject_id"] = "Unknown"
            if "species" not in subject_metadata:
                subject_metadata["species"] = "Unknown species"
            if "sex" not in subject_metadata:
                subject_metadata["sex"] = "U"

            if "Subject" in metadata and isinstance(metadata["Subject"], dict):
                metadata["Subject"].update(subject_metadata)
            else:
                metadata["Subject"] = subject_metadata

        return metadata
