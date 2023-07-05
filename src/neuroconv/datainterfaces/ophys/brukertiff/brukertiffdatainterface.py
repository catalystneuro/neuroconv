from copy import deepcopy
from typing import Literal, Optional
from warnings import warn

from dateutil.parser import parse
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....tools.roiextractors import add_imaging
from ....utils import FolderPathType
from ....utils.dict import DeepDict


class BrukerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for BrukerTiffImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The path that points to the folder containing the Bruker TIF image files and configuration files."
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        plane_separation_type: Optional[Literal["contiguous", "disjoint"]] = None,
        verbose: bool = True,
    ):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : FolderPathType
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        plane_separation_type: {'contiguous', 'disjoint'}
            Defines how to write volumetric imaging data. The default behavior is to assume the planes are contiguous,
            and the imaging plane is a volume. Use 'disjoint' for writing them as a separate plane.
        verbose : bool, default: True
        """
        self.plane_separation_type = plane_separation_type
        super().__init__(folder_path=folder_path, verbose=verbose)
        self._image_size = self.imaging_extractor.get_image_size()
        # we can also check if the difference in the changing z positions are equal to
        # the number of microns per pixel (5) then we know its volumetric
        # that is probably better once the multicolor example gets in the picture
        if len(self._image_size) == 3 and plane_separation_type not in ["disjoint", "contiguous"]:
            raise AssertionError(
                "For volumetric imaging data the plane separation method must be one of 'disjoint' or 'contiguous'."
            )
        if plane_separation_type is not None and len(self._image_size) == 2:
            warn("The plane separation method is ignored for non-volumetric data.")
        # for disjoint planes the frame rate should be divided by the number of planes
        if plane_separation_type is "disjoint" and len(self._image_size) == 3:
            self.imaging_extractor._sampling_frequency /= self._image_size[-1]

    def update_metadata_for_disjoint_planes(self, metadata: DeepDict) -> DeepDict:
        num_z_planes = self._image_size[-1]

        first_imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"].pop(0)
        first_two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"].pop(0)

        positions = self.imaging_extractor.xml_metadata["positionCurrent"][:num_z_planes]
        for plane_num in range(num_z_planes):
            # TODO: not always the last is the variable z-axis parameter
            z_position = positions[plane_num][-1]["ZAxis"]
            z_position_value = float(z_position["value"]) / 1e6

            imaging_plane_metadata = deepcopy(first_imaging_plane_metadata)
            imaging_plane_name = f"ImagingPlane{plane_num + 1}"
            imaging_plane_metadata.update(
                name=imaging_plane_name,
                description=f"The plane {plane_num + 1} imaged at {z_position_value} meters by the microscope.",
            )
            metadata["Ophys"]["ImagingPlane"].append(imaging_plane_metadata)

            two_photon_series_metadata = deepcopy(first_two_photon_series_metadata)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{plane_num + 1}",
                description=f"The imaging data for plane {plane_num + 1} acquired from the Bruker Two-Photon Microscope.",
                imaging_plane=imaging_plane_name,
                field_of_view=two_photon_series_metadata["field_of_view"].pop(-1),
            )
            metadata["Ophys"]["TwoPhotonSeries"].append(two_photon_series_metadata)

        return metadata

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

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
        z_plane_position_in_meters = float(microns_per_pixel[2]["ZAxis"]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters]
        if len(self._image_size) == 3:
            grid_spacing.append(z_plane_position_in_meters)

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing, description=f"The plane imaged at {z_plane_position_in_meters} meters depth."
        )

        field_of_view = [
            y_position_in_meters * self._image_size[1],
            x_position_in_meters * self._image_size[0],
            z_plane_position_in_meters,  # for disjoint planes this should be 2D
        ]
        two_photon_series_metadata.update(field_of_view=field_of_view)

        if self.plane_separation_type == "disjoint" and len(self._image_size) == 3:
            return self.update_metadata_for_disjoint_planes(metadata=metadata)
        if self.plane_separation_type == "contiguous" and len(self._image_size) == 3:
            two_photon_series_metadata.update(
                description="The volumetric imaging data acquired from the Bruker Two-Photon Microscope."
            )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        extractor_image_size = self.imaging_extractor.get_image_size()
        if (self.plane_separation_type == "contiguous") or len(extractor_image_size) == 2:
            return super().add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_type=photon_series_type,
                stub_test=stub_test,
                stub_frames=stub_frames,
            )

        num_z_planes = self.imaging_extractor.get_image_size()[-1]
        for plane_num in range(num_z_planes):
            imaging_extractor = self.imaging_extractor.depth_slice(start_plane=plane_num, end_plane=plane_num + 1)
            add_imaging(
                imaging=imaging_extractor,
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_type=photon_series_type,
            )
