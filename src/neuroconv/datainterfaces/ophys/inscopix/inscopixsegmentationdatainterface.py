from pydantic import FilePath, validate_call

from neuroconv.datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Conversion interface for Inscopix segmentation data."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix segmentation."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = True,
    ):
        super().__init__(file_path=file_path, verbose=verbose)
        
    def get_metadata(self) -> dict:
        """Get metadata formatted for NWB conversion.
        
        Returns
        -------
        dict
            Metadata dictionary formatted for NWB file creation.
            
        Notes
        -----
        This method extracts comprehensive metadata from Inscopix files including:
        - Device and imaging parameters
        - Subject information (defaults to Mus musculus if not specified)
        - Session timing and experimental details
        - Analysis method information
        """
        metadata = super().get_metadata()
    
        # --- Session start time ---
        session_start_time = self.segmentation_extractor.get_session_start_time()
        if session_start_time:
            metadata.setdefault("NWBFile", {})["session_start_time"] = session_start_time

        # --- Device metadata ---
        device_info = self.segmentation_extractor.get_device_info()
        metadata.setdefault("Ophys", {}).setdefault("Device", [{}])
        
        if device_info and any(device_info.values()):
            device_metadata = metadata["Ophys"]["Device"][0]
            
            if device_info.get("device_name"):
                device_metadata["name"] = device_info["device_name"]
            
            description_parts = self._build_device_description(device_info)
            if description_parts:
                device_metadata["description"] = "; ".join(description_parts)

        # --- Imaging plane metadata ---
        imaging_info = self.segmentation_extractor.get_imaging_info()
        session_info = self.segmentation_extractor.get_session_info()
        
        metadata.setdefault("Ophys", {}).setdefault("ImagingPlane", [{}])
        
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        self._populate_imaging_plane_metadata(
            imaging_plane_metadata, imaging_info, session_info, device_info
        )

        # --- Analysis metadata ---
        analysis_info = self.segmentation_extractor.get_analysis_info()
        self._populate_analysis_metadata(metadata, analysis_info)

        # --- Subject metadata ---
        subject_info = self.segmentation_extractor.get_subject_info()
        metadata.setdefault("Subject", {})
        self._populate_subject_metadata(metadata["Subject"], subject_info)

        # --- Session metadata ---
        if session_info:
            self._populate_session_metadata(metadata, session_info, subject_info)

        return metadata
    
    def _build_device_description(self, device_info: dict) -> list:
        """Build device description from available device information."""
        description_parts = []
        
        if device_info.get("device_name"):
            description_parts.append(f"Inscopix {device_info['device_name']}")
        if device_info.get("device_serial_number"):
            description_parts.append(f"Serial: {device_info['device_serial_number']}")
        if device_info.get("acquisition_software_version"):
            description_parts.append(f"Software version {device_info['acquisition_software_version']}")
            
        return description_parts
    
    def _populate_imaging_plane_metadata(self, imaging_plane_metadata: dict, 
                                       imaging_info: dict, session_info: dict, 
                                       device_info: dict):
        """Populate imaging plane metadata from extracted information."""
        # Link to device 
        if device_info and device_info.get("device_name"):
            imaging_plane_metadata["device"] = device_info["device_name"]
        
        # Update description 
        description_parts = ["Inscopix imaging plane"]
        if imaging_info and imaging_info.get("field_of_view_pixels"):
            fov = imaging_info["field_of_view_pixels"]
            description_parts.append(f"field of view {fov[1]}x{fov[0]} pixels")
        imaging_plane_metadata["description"] = " with ".join(description_parts)

        # Set imaging rate 
        if session_info and session_info.get("sampling_rate_hz"):
            imaging_plane_metadata["imaging_rate"] = session_info["sampling_rate_hz"]

        # Optical channel 
        if imaging_info and imaging_info.get("channel"):
            channel = imaging_info["channel"]
            optical_channel = {
                "name": f"OpticalChannel{channel.capitalize()}",
                "description": f"Inscopix {channel} channel",
                "emission_lambda": float('nan') # Default to NaN if not specified
            }
            
            if imaging_info.get("emission_lambda"):
                optical_channel["emission_lambda"] = float(imaging_info["emission_lambda"])
            
            imaging_plane_metadata["optical_channel"] = [optical_channel]
        else:
            # Default optical channel if not specified
            imaging_plane_metadata["optical_channel"] = [{
                "name": "OpticalChannelDefault",
                "description": "Inscopix optical channel",
                "emission_lambda": float('nan')
            }]
    
    def _populate_analysis_metadata(self, metadata: dict, analysis_info: dict):
        """Populate analysis metadata from extracted information."""
        description_parts = ["Inscopix cell segmentation"]
        
        if analysis_info.get("cell_identification_method"):
            description_parts.append(f"using {analysis_info['cell_identification_method']}")
        if analysis_info.get("trace_units"):
            description_parts.append(f"with traces in {analysis_info['trace_units']}")
        
        metadata.setdefault("Ophys", {}).setdefault("ImageSegmentation", {})
        metadata["Ophys"]["ImageSegmentation"]["description"] = " ".join(description_parts)
    
    def _populate_subject_metadata(self, subject_metadata: dict, subject_info: dict):
        """Populate subject metadata with required and optional fields."""
        # Required field: subject_id
        if subject_info and subject_info.get("animal_id"):
            subject_metadata["subject_id"] = subject_info["animal_id"]
        else:
            subject_metadata["subject_id"] = "Unknown"
        
        # Required field: species (default to Mus musculus --> how to map to CaMKIICre?)
        subject_metadata["species"] = "Mus musculus"
    
        sex_mapping = {
            "m": "M", "male": "M", 
            "f": "F", "female": "F",
            "u": "U", "unknown": "U"
        }

        if subject_info and subject_info.get("sex"):
            subject_metadata["sex"] = sex_mapping.get(subject_info["sex"].lower(), "U")
        else:
            subject_metadata["sex"] = "U"  

        if subject_info:
            if subject_info.get("description"):
                subject_metadata["description"] = subject_info["description"]
            
            if subject_info.get("date_of_birth"):
                subject_metadata["date_of_birth"] = subject_info["date_of_birth"]
            
            if subject_info.get("weight") and subject_info["weight"] > 0:
                subject_metadata["weight"] = subject_info["weight"]
    
    def _populate_session_metadata(self, metadata: dict, session_info: dict, subject_info: dict):
        """Populate session-level metadata."""
        metadata.setdefault("NWBFile", {})
        
        if session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        session_parts = []
        if session_info.get("session_name"):
            session_parts.append(f"Session: {session_info['session_name']}")
        if subject_info and subject_info.get("description"):
            session_parts.append(subject_info["description"])
        
        if session_parts:
            metadata["NWBFile"]["session_description"] = "; ".join(session_parts)