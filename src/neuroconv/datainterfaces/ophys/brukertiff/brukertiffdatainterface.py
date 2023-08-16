from copy import deepcopy
from typing import Literal, Optional
from warnings import warn

from dateutil.parser import parse
from pynwb import NWBFile

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
        channel_stream_name = streams["channel_streams"][0]
        if plane_separation_type == "contiguous":
            streams["plane_streams"].update({channel_stream_name: [streams["plane_streams"][channel_stream_name][0]]})
        return streams

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_name: Optional[str] = None,
        plane_separation_type: Literal["contiguous", "disjoint"] = None,
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
        plane_separation_type: {'contiguous', 'disjoint'}
            Defines how to write volumetric imaging data. The default behavior is to assume the planes are contiguous,
            and the imaging plane is a volume. Use 'disjoint' for writing them as a separate plane.
        verbose : bool, default: True
        """
        self.streams = self.get_streams(folder_path=folder_path, plane_separation_type=plane_separation_type)
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._image_size = self.imaging_extractor.get_image_size()

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

        if len(self.streams["channel_streams"]) > 1:
            imaging_plane_name = f"ImagingPlane{self._stream_name}"
            imaging_plane_metadata.update(name=imaging_plane_name)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{self._stream_name}",
                imaging_plane=imaging_plane_name,
            )

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
        z_plane_position_in_meters = float(microns_per_pixel[2]["ZAxis"]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters, z_plane_position_in_meters]
        field_of_view = [
            y_position_in_meters * self._image_size[1],
            x_position_in_meters * self._image_size[0],
            z_plane_position_in_meters,
        ]

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing, description=f"The plane imaged at {z_plane_position_in_meters} meters depth."
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
        self.folder_path = folder_path
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._image_size = self.imaging_extractor.get_image_size()

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
            unit="px",
            format="tiff",
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
        z_plane_position_in_meters = float(microns_per_pixel[2]["ZAxis"]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters]
        field_of_view = [
            y_position_in_meters * self._image_size[1],
            x_position_in_meters * self._image_size[0],
        ]

        if len(streams["plane_streams"]):
            num_planes_per_channel_stream = len(list(streams["plane_streams"].values())[0])
            z_plane_position_in_meters /= num_planes_per_channel_stream
        imaging_plane_metadata.update(
            grid_spacing=grid_spacing, description=f"The plane imaged at {z_plane_position_in_meters} meters depth."
        )
        two_photon_series_metadata.update(field_of_view=field_of_view)

        return metadata
