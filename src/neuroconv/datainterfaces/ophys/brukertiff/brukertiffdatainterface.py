from typing import List, Literal, Optional

from dateutil.parser import parse

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FolderPathType
from ....utils.dict import DeepDict


class BrukerTiffMultiPlaneImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for BrukerTiffMultiPlaneImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The path that points to the folder containing the Bruker volumetric TIF image files and configuration files."
        return source_schema

    @classmethod
    def get_streams(
        cls,
        folder_path: FolderPathType,
        plane_separation_type: Literal["contiguous", "disjoint"] = None,
    ) -> dict:
        from roiextractors import BrukerTiffMultiPlaneImagingExtractor

        streams = BrukerTiffMultiPlaneImagingExtractor.get_streams(folder_path=folder_path)
        for channel_stream_name in streams["channel_streams"]:
            if plane_separation_type == "contiguous":
                streams["plane_streams"].update(
                    {channel_stream_name: [streams["plane_streams"][channel_stream_name][0]]}
                )
        return streams

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_name: Optional[str] = None,
        verbose: bool = True,
    ):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : FolderPathType
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        stream_name : str, optional
            The name of the recording stream (e.g. 'Ch2').
        verbose : bool, default: True
        """
        self.folder_path = folder_path
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._image_size = self.imaging_extractor.get_image_size()

    def _determine_position_current(self) -> List[float]:
        """
        Returns y, x, and z position values. The unit of values is in the microscope reference frame.
        """
        from roiextractors.extractors.tiffimagingextractors.brukertiffimagingextractor import (
            _parse_xml,
        )

        streams = self.get_streams(folder_path=self.folder_path)
        channel_stream_name = streams["channel_streams"][0]
        plane_streams_per_channel = streams["plane_streams"][channel_stream_name]

        # general positionCurrent
        position_values = []
        xml_root_element = _parse_xml(folder_path=self.folder_path)
        default_position_element = xml_root_element.find(".//PVStateValue[@key='positionCurrent']")

        for index_value in ["YAxis", "XAxis"]:
            position_sub_indexed_values = default_position_element.find(f"./SubindexedValues[@index='{index_value}']")
            for position_sub_indexed_value in position_sub_indexed_values:
                position_values.append(float(position_sub_indexed_value.attrib["value"]))

        z_plane_values = []
        for plane_stream in plane_streams_per_channel:
            frames_per_stream = [
                frame
                for frame in xml_root_element.findall(".//Frame")
                for file in frame.findall("File")
                if plane_stream in file.attrib["filename"]
            ]

            # The frames for each plane will have the same positionCurrent values
            position_element = frames_per_stream[0].find(".//PVStateValue[@key='positionCurrent']")
            default_z_position_values = default_position_element.find(f"./SubindexedValues[@index='ZAxis']")
            z_positions = []
            for z_sub_indexed_value in default_z_position_values:
                z_value = float(z_sub_indexed_value.attrib["value"])
                z_positions.append(z_value)

            z_position_values = position_element.find("./SubindexedValues[@index='ZAxis']")
            for z_device_ind, z_position_value in enumerate(z_position_values):
                z_value = float(z_position_value.attrib["value"])
                # find the changing z position value
                if z_positions[z_device_ind] != z_value:
                    z_plane_values.append(z_value)

        # difference between start position and end position of the z scan
        if len(z_plane_values) > 1:
            z_value = abs(z_plane_values[0] - z_plane_values[-1])
        position_values.append(z_value)
        return position_values

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = parse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "BrukerFluorescenceMicroscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"][0]
        two_photon_series_metadata.update(
            description="The volumetric imaging data acquired from the Bruker Two-Photon Microscope.",
            scan_line_rate=1 / float(xml_metadata["scanLinePeriod"]),
        )

        streams = self.get_streams(folder_path=self.folder_path, plane_separation_type="contiguous")
        if len(streams["channel_streams"]) > 1:
            imaging_plane_name = f"ImagingPlane{self._stream_name}"
            imaging_plane_metadata.update(name=imaging_plane_name)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{self._stream_name}",
                imaging_plane=imaging_plane_name,
            )

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6

        origin_coords = self._determine_position_current()
        z_plane_current_position_in_meters = abs(origin_coords[-1]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters, z_plane_current_position_in_meters]
        field_of_view = [
            y_position_in_meters * self._image_size[1],
            x_position_in_meters * self._image_size[0],
            z_plane_current_position_in_meters,
        ]

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing,
            origin_coords=origin_coords,
            description=f"The imaging plane origin_coords units are in the microscope reference frame.",
        )

        two_photon_series_metadata.update(field_of_view=field_of_view)

        return metadata


class BrukerTiffSinglePlaneImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for BrukerTiffSinglePlaneImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The path that points to the folder containing the Bruker TIF image files and configuration files."
        return source_schema

    @classmethod
    def get_streams(cls, folder_path: FolderPathType) -> dict:
        from roiextractors import BrukerTiffMultiPlaneImagingExtractor

        streams = BrukerTiffMultiPlaneImagingExtractor.get_streams(folder_path=folder_path)
        return streams

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_name: Optional[str] = None,
        verbose: bool = True,
    ):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : FolderPathType
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        stream_name : str, optional
            The name of the recording stream (e.g. 'Ch2').
        verbose : bool, default: True
        """
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )
        self._determine_position_current()
        self.folder_path = folder_path
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._image_size = self.imaging_extractor.get_image_size()

    def _determine_position_current(self) -> List[float]:
        """
        Returns y, x, and z position values. The unit of values is in the microscope reference frame.
        """
        stream_name = self.imaging_extractor.stream_name
        frames_per_stream = [
            frame
            for frame in self.imaging_extractor._xml_root.findall(".//Frame")
            for file in frame.findall("File")
            if stream_name in file.attrib["filename"]
        ]

        # general positionCurrent
        position_values = []
        default_position_element = self.imaging_extractor._xml_root.find(".//PVStateValue[@key='positionCurrent']")

        for index_value in ["YAxis", "XAxis"]:
            position_sub_indexed_values = default_position_element.find(f"./SubindexedValues[@index='{index_value}']")
            for position_sub_indexed_value in position_sub_indexed_values:
                position_values.append(float(position_sub_indexed_value.attrib["value"]))

        # The frames for each plane will have the same positionCurrent values
        position_element = frames_per_stream[0].find(".//PVStateValue[@key='positionCurrent']")
        if not position_element:
            return position_values

        default_z_position_values = default_position_element.find(f"./SubindexedValues[@index='ZAxis']")
        z_positions = []
        for z_sub_indexed_value in default_z_position_values:
            z_positions.append(float(z_sub_indexed_value.attrib["value"]))

        z_position_values = position_element.find("./SubindexedValues[@index='ZAxis']")
        for z_device_ind, z_position_value in enumerate(z_position_values):
            z_value = float(z_position_value.attrib["value"])
            # find the changing z position value
            if z_positions[z_device_ind] != z_value:
                position_values.append(z_value)

        return position_values

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = parse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "BrukerFluorescenceMicroscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"][0]

        two_photon_series_metadata.update(
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            scan_line_rate=1 / float(xml_metadata["scanLinePeriod"]),
        )

        streams = self.get_streams(folder_path=self.folder_path)
        if len(streams["channel_streams"]) > 1 or len(streams["plane_streams"]):
            imaging_plane_name = f"ImagingPlane{self._stream_name}"
            imaging_plane_metadata.update(name=imaging_plane_name)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{self._stream_name}",
                imaging_plane=imaging_plane_name,
            )

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters]
        origin_coords = self._determine_position_current()
        field_of_view = [
            y_position_in_meters * self._image_size[1],
            x_position_in_meters * self._image_size[0],
        ]

        if len(streams["plane_streams"]) and len(origin_coords) == 3:
            z_plane_current_position_in_meters = abs(origin_coords[-1]) / 1e6
            grid_spacing.append(z_plane_current_position_in_meters)
            field_of_view.append(z_plane_current_position_in_meters)

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing,
            origin_coords=origin_coords,
            description="The imaging plane origin_coords units are in the microscope reference frame.",
        )
        two_photon_series_metadata.update(field_of_view=field_of_view)

        return metadata
