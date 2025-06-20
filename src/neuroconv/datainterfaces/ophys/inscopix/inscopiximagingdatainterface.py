from typing import Optional

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


def is_file_multiplane(file_path):
    """
    Hacky check for 'multiplane' keyword in the file.
    Reads line by line to avoid memory issues with large files.
    If found, raises NotImplementedError.
    This is NOT a proper ISX API method—just a string search.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "multiplane" in line:
                raise NotImplementedError(
                    f"Multiplane ISXD file detected (found 'multiplane' in file).\n"
                    f"This is a hacky check (not an official ISX API method) and may not be robust.\n"
                    f"Proper separation logic is not yet implemented in roiextractors.\n"
                    f"Loading as 2D would result in incorrect data interpretation.\n\n"
                    f"Please open an issue at:\n"
                    f"https://github.com/catalystneuro/roiextractors/issues\n\n"
                    f"Reference: https://github.com/inscopix/pyisx/issues/36"
                )


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
        **kwargs,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the .isxd Inscopix file.
        verbose : bool, optional
            If True, outputs additional information during processing.
        **kwargs : dict, optional
            Additional keyword arguments passed to the parent class.

        Raises
        ------
        NotImplementedError
            If the file contains multiplane configuration that is not yet supported.
        """
        # Check for multiplane configuration before proceeding
        is_file_multiplane(file_path)

        kwargs.setdefault("photon_series_type", "OnePhotonSeries")
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            **kwargs,
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
        # Get metadata from parent (already configured for OnePhotonSeries)
        metadata = super().get_metadata()

        extractor = self.imaging_extractor
        extractor_metadata = extractor._get_metadata()

        # Extract individual components
        session_info = extractor_metadata.get("session", {})
        device_info = extractor_metadata.get("device", {})
        subject_info = extractor_metadata.get("subject", {})
        session_start_time = extractor_metadata.get("session_start_time")

        # Session start time
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Session name and experimenter
        if session_info.get("session_name"):
            metadata["NWBFile"]["session_id"] = session_info["session_name"]
        if session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        # Device information
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

        # Subject information
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
            # If it contains genotype info or matches NWB format, put it in species; otherwise strain
            # e.g., "CaMKIICre"
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

        # Sex mapping
        sex_mapping = {"m": "M", "male": "M", "f": "F", "female": "F", "u": "U", "unknown": "U"}
        if subject_info and subject_info.get("sex"):
            mapped_sex = sex_mapping.get(subject_info["sex"].lower(), "U")
            subject_metadata["sex"] = mapped_sex
            has_any_subject_data = True

        # Additional subject fields
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

            if "Subject" in metadata:
                metadata["Subject"].update(subject_metadata)
            else:
                metadata["Subject"] = subject_metadata

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: Optional[dict] = None,
        **kwargs,
    ):
        """
        Add the Inscopix data to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            NWB file to add the data to.
        metadata : dict, optional
            Metadata dictionary. If None, will be generated dynamically with OnePhotonSeries.
        **kwargs
            Additional keyword arguments passed to the parent add_to_nwbfile method.

        # TODO: add logic for determining whether the microscope is `nVista 2P` and change photon_series_type to TwoPhotonSeries accordingly.
        """
        kwargs["photon_series_type"] = "OnePhotonSeries"
        # TODO: add logic for determining whether the microscope is `nVista 2P` and change photon_series_type to TwoPhotonSeries accordingly.
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **kwargs)
