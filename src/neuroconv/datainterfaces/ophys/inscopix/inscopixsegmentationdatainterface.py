from pydantic import FilePath, validate_call
import warnings

from neuroconv.datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Conversion interface for Inscopix segmentation data."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix segmentation."

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = True):
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self) -> dict:
        """Get metadata formatted for NWB conversion."""
        metadata = super().get_metadata()

        # Get all info from extractor using updated method names - handle None cases with try-except for empty datasets
        try:
            device_info = self.segmentation_extractor.get_device_info()
        except AttributeError:
            device_info = {}
        
        try:
            session_info = self.segmentation_extractor.get_session_info()
        except AttributeError:
            session_info = {}
            
        try:
            subject_info = self.segmentation_extractor.get_subject_info()
        except AttributeError:
            subject_info = {}
        
        try:
            analysis_info = self.segmentation_extractor.get_analysis_info()
        except AttributeError:
            analysis_info = {}
        
        try:
            probe_info = self.segmentation_extractor.get_probe_info()
        except AttributeError:
            probe_info = {}

        try:
            session_start_time = self.segmentation_extractor.get_session_start_time()
        except AttributeError:
            session_start_time = None
        
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Experimenter and session description
        if session_info and session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        if session_info and session_info.get("session_name"):
            session_desc = f"Session: {session_info['session_name']}"
            if subject_info and subject_info.get("description"):
                session_desc += f"; {subject_info['description']}"
            metadata["NWBFile"]["session_description"] = session_desc

        device = metadata["Ophys"]["Device"][0]

        if device_info and device_info.get("device_name"):
            device["name"] = device_info["device_name"]

        device_desc_parts = []
        if device_info and device_info.get("device_name"):
            device_desc_parts.append(f"Inscopix {device_info['device_name']}")
        if device_info and device_info.get("device_serial_number"):
            device_desc_parts.append(f"Serial: {device_info['device_serial_number']}")
        if device_info and device_info.get("acquisition_software_version"):
            device_desc_parts.append(f"Software version {device_info['acquisition_software_version']}")
        if probe_info:
            for field in [
                "Probe Diameter (mm)",
                "Probe Flip",
                "Probe Length (mm)",
                "Probe Pitch",
                "Probe Rotation (degrees)",
                "Probe Type",
            ]:
                value = probe_info.get(field)
                if value is not None:
                    device_desc_parts.append(f"{field}: {value}")
        if device_desc_parts:
            device["description"] = "; ".join(device_desc_parts)

        # Imaging plane
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]

        if device_info and device_info.get("device_name"):
            imaging_plane["device"] = device_info["device_name"]

        plane_desc = "Inscopix imaging plane"
        if device_info and device_info.get("field_of_view_pixels"):
            fov = device_info["field_of_view_pixels"]
            plane_desc += f" with field of view {fov[1]}x{fov[0]} pixels"
        
        desc_parts = [plane_desc]
        if device_info and device_info.get("microscope_focus"):
            desc_parts.append(f"Focus: {device_info['microscope_focus']} µm")
        if device_info and device_info.get("exposure_time_ms"):
            desc_parts.append(f"Exposure: {device_info['exposure_time_ms']} ms")
        if device_info and device_info.get("microscope_gain"):
            desc_parts.append(f"Gain: {device_info['microscope_gain']}")
        
        imaging_plane["description"] = "; ".join(desc_parts)

        #Sampling frequency
        try:
            sampling_frequency = self.segmentation_extractor.get_sampling_frequency()
        except AttributeError:
            sampling_frequency = None
        
        if sampling_frequency:
            imaging_plane["imaging_rate"] = sampling_frequency

        # Optical channel
        optical_channel = {
            "name": "OpticalChannelDefault",
            "description": "Inscopix optical channel",
            "emission_lambda": float("nan"),
        }
        if device_info and device_info.get("channel"):
            channel = device_info["channel"]
            optical_channel["name"] = f"OpticalChannel{channel.capitalize()}"
            optical_channel["description"] = f"Inscopix {channel} channel"
        
        # LED power
        if device_info and device_info.get("led_power_1_mw_per_mm2"):
            led_power = device_info["led_power_1_mw_per_mm2"]
            optical_channel["description"] += f" (LED power: {led_power} mW/mm²)"
        
        imaging_plane["optical_channel"] = [optical_channel]

        # Image segmentation
        segmentation_desc = "Inscopix cell segmentation"
        if analysis_info and analysis_info.get("cell_identification_method"):
            segmentation_desc += f" using {analysis_info['cell_identification_method']}"
        if analysis_info and analysis_info.get("trace_units"):
            segmentation_desc += f" with traces in {analysis_info['trace_units']}"
        
        # Add number of ROIs to description
        num_rois = self.segmentation_extractor.get_num_rois()
        segmentation_desc += f" ({num_rois} ROIs identified)"
        
        metadata["Ophys"]["ImageSegmentation"]["description"] = segmentation_desc

        # Subject
        subject = metadata["Subject"]

        if subject_info and subject_info.get("animal_id"):
            subject["subject_id"] = subject_info["animal_id"]
        else:
            subject["subject_id"] = "Unknown"

        # Species validation - check if it matches expected format
        species_value = None
        strain_value = None
        
        if subject_info and subject_info.get("species"):
            species_raw = subject_info["species"]
            # If it contains genotype info or doesn't match format, put it in strain instead
            if " " in species_raw and species_raw[0].isupper() and species_raw.split()[1][0].islower():
                species_value = species_raw
            else:
                strain_value = species_raw
        
        subject["species"] = species_value if species_value else "Unknown species" 
        if strain_value:
            subject["strain"] = strain_value

        # Sex mapping
        sex_mapping = {"m": "M", "male": "M", "f": "F", "female": "F", "u": "U", "unknown": "U"}
        if subject_info and subject_info.get("sex"):
            subject["sex"] = sex_mapping.get(subject_info["sex"].lower(), "U")
        else:
            subject["sex"] = "U"

        # Optional subject fields
        if subject_info:
            if subject_info.get("description"):
                subject["description"] = subject_info["description"]
            if subject_info.get("date_of_birth"):
                subject["date_of_birth"] = subject_info["date_of_birth"]
            if subject_info.get("weight") and subject_info["weight"] > 0:
                subject["weight"] = subject_info["weight"]

        return metadata