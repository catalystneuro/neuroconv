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
    def __init__(self, file_path: FilePath, verbose: bool = True):
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self) -> dict:
        """Get metadata formatted for NWB conversion."""
        metadata = super().get_metadata()
        
        # Get all info from extractor
        device_info = self.segmentation_extractor.get_device_info()
        imaging_info = self.segmentation_extractor.get_imaging_info()
        session_info = self.segmentation_extractor.get_session_info()
        subject_info = self.segmentation_extractor.get_subject_info()
        analysis_info = self.segmentation_extractor.get_analysis_info()
        
        # Session start time
        session_start_time = self.segmentation_extractor.get_session_start_time()
        if session_start_time:
            metadata.setdefault("NWBFile", {})["session_start_time"] = session_start_time
        
        # Experimenter and session description
        if session_info.get("experimenter_name"):
            metadata.setdefault("NWBFile", {})["experimenter"] = [session_info["experimenter_name"]]
        
        if session_info.get("session_name"):
            session_desc = f"Session: {session_info['session_name']}"
            if subject_info and subject_info.get("description"):
                session_desc += f"; {subject_info['description']}"
            metadata.setdefault("NWBFile", {})["session_description"] = session_desc
        
        # Device
        metadata.setdefault("Ophys", {}).setdefault("Device", [{}])
        device = metadata["Ophys"]["Device"][0]
        
        if device_info.get("device_name"):
            device["name"] = device_info["device_name"]
            
        device_desc_parts = []
        if device_info.get("device_name"):
            device_desc_parts.append(f"Inscopix {device_info['device_name']}")
        if device_info.get("device_serial_number"):
            device_desc_parts.append(f"Serial: {device_info['device_serial_number']}")
        if device_info.get("acquisition_software_version"):
            device_desc_parts.append(f"Software version {device_info['acquisition_software_version']}")
        if device_desc_parts:
            device["description"] = "; ".join(device_desc_parts)
        
        # Imaging plane
        metadata.setdefault("Ophys", {}).setdefault("ImagingPlane", [{}])
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        
        if device_info and device_info.get("device_name"):
            imaging_plane["device"] = device_info["device_name"]
        
        plane_desc = "Inscopix imaging plane"
        if imaging_info and imaging_info.get("field_of_view_pixels"):
            fov = imaging_info["field_of_view_pixels"]
            plane_desc += f" with field of view {fov[1]}x{fov[0]} pixels"
        imaging_plane["description"] = plane_desc
        
        if session_info and session_info.get("sampling_rate_hz"):
            imaging_plane["imaging_rate"] = session_info["sampling_rate_hz"]
        
        # Optical channel
        optical_channel = {
            "name": "OpticalChannelDefault",
            "description": "Inscopix optical channel",
            "emission_lambda": float("nan"),
        }
        if imaging_info and imaging_info.get("channel"):
            channel = imaging_info["channel"]
            optical_channel["name"] = f"OpticalChannel{channel.capitalize()}"
            optical_channel["description"] = f"Inscopix {channel} channel"
        if imaging_info and imaging_info.get("emission_lambda"):
            optical_channel["emission_lambda"] = float(imaging_info["emission_lambda"])
        imaging_plane["optical_channel"] = [optical_channel]
        
        # Image segmentation
        segmentation_desc = "Inscopix cell segmentation"
        if analysis_info.get("cell_identification_method"):
            segmentation_desc += f" using {analysis_info['cell_identification_method']}"
        if analysis_info.get("trace_units"):
            segmentation_desc += f" with traces in {analysis_info['trace_units']}"
        metadata.setdefault("Ophys", {}).setdefault("ImageSegmentation", {})["description"] = segmentation_desc
        
        # Subject
        metadata.setdefault("Subject", {})
        subject = metadata["Subject"]

        if subject_info and subject_info.get("animal_id"):
            subject["subject_id"] = subject_info["animal_id"]
        else:
            subject["subject_id"] = "Unknown"
        subject["species"] = "Mus musculus" # how to handle species to be compatible with NWB 'CaMKIICre' 
        # authorized : "^[A-Z][a-z]+ [a-z]+|http://purl.obolibrary.org/obo/NCBITaxon_[0-9]+"
        
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