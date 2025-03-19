"""Interface for Thor TIFF files with OME metadata."""

from datetime import datetime, timezone
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class ThorImagingInterface(BaseImagingExtractorInterface):
    """
    Interface for Thor TIFF files with OME metadata.

    This interface is designed to work with data acquired using ThorImageLS software
    (not to be confused with the ThorLabs hardware itself). The interface reads TIFF files
    exported by ThorImageLS software, which follows the OME-TIFF standard, along with an
    Experiment.xml file that contains metadata about the acquisition.

    Note that it is possible that data was acquired with a Thor microscope but not with
    the ThorImageLS software, in which case this interface may not work correctly.
    """

    display_name = "ThorLabs TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for Thor TIFF files Exporter with ThorImageLS."
    ExtractorName = "ThorTiffImagingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Thor imaging interface.

        Returns
        -------
        dict
            The JSON schema for the Thor imaging interface source data,
            containing file path and channel name parameters.
        """
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])

        return source_schema

    @validate_call
    def __init__(self, file_path: FilePath, channel_name: Optional[str] = None, verbose: bool = False):
        """
        Initialize reading of a TIFF file.

        Parameters
        ----------
        file_path : FilePath
            Path to first OME TIFF file (e.g., ChanA_001_001_001_001.tif)
        channel_name : str, optional
            Name of the channel to extract (must match name in Experiment.xml)
        verbose : bool, default: False
            If True, print verbose output
        """

        super().__init__(file_path=file_path, channel_name=channel_name, verbose=verbose)
        self.channel_name = channel_name

    def get_metadata(self) -> DeepDict:
        """
        Retrieve the metadata for the Thor imaging data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            and photon series configuration.
        """
        metadata = super().get_metadata()

        # Access the experiment XML dictionary from the extractor
        xml_dict = self.imaging_extractor._experiment_xml_dict
        thor_experiment = xml_dict["ThorImageExperiment"]

        # Device metadata
        software = thor_experiment["Software"]
        software_version = software["@version"]
        device_description = f"ThorLabs 2P Microscope running ThorImageLS {software_version}"

        # Session start time
        date_info = thor_experiment["Date"]
        if isinstance(date_info, list):
            # Locate the first entry that contains "date"
            first_entry_with_date = next((entry for entry in date_info if "@date" in entry), None)
            unix_timestamps = first_entry_with_date["@uTime"]
        else:
            unix_timestamps = date_info["@uTime"]

        self.session_start_time = datetime.fromtimestamp(float(unix_timestamps), tz=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = self.session_start_time

        metadata.setdefault("Ophys", {})["Device"] = [{"name": "ThorMicroscope", "description": device_description}]

        # LSM metadata
        lsm = thor_experiment["LSM"]
        pixel_size = float(lsm["@pixelSizeUM"])
        width_um = float(lsm["@widthUM"])
        height_um = float(lsm["@heightUM"])

        ChannelName = _to_camel_case(self.channel_name)

        optical_channel_dict = {"name": ChannelName, "description": "", "emission_lambda": np.nan}
        optical_channels = [optical_channel_dict]

        imaging_plane_name = f"ImagingPlane{ChannelName}"
        channel_imaging_plane_metadata = {
            "name": imaging_plane_name,
            "optical_channel": optical_channels,
            "description": "2P Imaging Plane",
            "device": "ThorMicroscope",
            "excitation_lambda": np.nan,  # Placeholder
            "indicator": "unknown",
            "location": "unknown",
            "grid_spacing": [pixel_size * 1e-6, pixel_size * 1e-6],  # Convert um to meters
            "grid_spacing_unit": "meters",
        }
        metadata["Ophys"]["ImagingPlane"] = [channel_imaging_plane_metadata]

        # TwoPhotonSeries metadata
        two_photon_series_name = f"TwoPhotonSeries{ChannelName}"
        two_photon_series_metadata = {
            "name": two_photon_series_name,
            "imaging_plane": imaging_plane_name,
            "field_of_view": [width_um * 1e-6, height_um * 1e-6],  # Convert um to meters
            "unit": "n.a.",
        }
        metadata["Ophys"]["TwoPhotonSeries"] = [two_photon_series_metadata]

        return metadata


def _to_camel_case(s: str) -> str:
    """
    Convert a string to CamelCase.

    Parameters
    ----------
    s : str
        Input string, potentially with underscores

    Returns
    -------
    str
        CamelCase string, or "Default" if input is empty
    """
    if not s:
        return "Default"
    parts = s.split("_")
    return parts[0] + "".join(word.title() for word in parts[1:])
