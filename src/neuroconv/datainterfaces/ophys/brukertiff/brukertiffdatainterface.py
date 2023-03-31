from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

import numpy as np
from dateutil.parser import parse

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FolderPathType


class BrukerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for BrukerTiffImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to Tiff folder."
        return source_schema

    def __init__(self, folder_path: FolderPathType, sampling_frequency: Optional[float] = None, verbose: bool = True):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        file_path : FilePathType
        sampling_frequency : float
        verbose : bool, default: True
        """
        super().__init__(folder_path=folder_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def _get_env_root(self):
        folder_path = Path(self.source_data["folder_path"])
        env_file_path = folder_path / f"{folder_path.stem}.env"
        assert env_file_path.is_file(), f"The ENV configuration file is not found at '{folder_path}'."
        tree = ElementTree.parse(env_file_path)
        return tree.getroot()

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = parse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "Bruker Fluorescence Microscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]

        root = self._get_env_root()
        laser_wavelength_param = root.find(".//NyquistSamplingController")
        if laser_wavelength_param:
            excitation_lambda = laser_wavelength_param.attrib["laserWavelength"]
            imaging_plane_metadata.update(excitation_lambda=float(excitation_lambda))

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        if microns_per_pixel:
            image_size = self.imaging_extractor.get_image_size()
            x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
            y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
            z_plane_position_in_meters = float(microns_per_pixel[2]["ZAxis"]) / 1e6
            grid_spacing = np.array([x_position_in_meters, y_position_in_meters]) / image_size
            imaging_plane_metadata.update(
                grid_spacing=grid_spacing, description=f"The plane imaged at {z_plane_position_in_meters} meters depth."
            )

        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        if xml_metadata["notes"]:
            metadata["NWBFile"].update(session_description=xml_metadata["notes"])

        return metadata
