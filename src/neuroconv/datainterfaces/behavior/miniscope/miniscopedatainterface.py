from pathlib import Path

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .... import BaseDataInterface
from ....tools import get_package
from ....utils import DeepDict


class MiniscopeBehaviorInterface(BaseDataInterface):
    """Data Interface for Miniscope behavior data."""

    display_name = "Miniscope Behavior"
    keywords = ("video",)
    associated_suffixes = (".avi",)
    info = "Interface for Miniscope behavior video data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The main Miniscope folder. The movie files are expected to be in sub folders within the main folder."
        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath):
        """
        Initialize reading recordings from the Miniscope behavioral camera.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path that points to the main Miniscope folder.
            The movie files are expected to be in sub folders within the main folder.
        """
        from ndx_miniscope.utils import (
            get_recording_start_times,
            get_starting_frames,
            get_timestamps,
            read_miniscope_config,
        )

        natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")

        super().__init__(folder_path=folder_path)

        folder_path = Path(self.source_data["folder_path"])
        self._behav_avi_file_paths = natsort.natsorted(list(folder_path.glob("*/BehavCam*/*.avi")))
        assert (
            self._behav_avi_file_paths
        ), f"The behavior movies (.avi files) are missing from '{self.source_data['folder_path']}'."
        # note we might have to change this if we have other examples
        configuration_file_name = "metaData.json"
        miniscope_config_files = natsort.natsorted(list(folder_path.glob(f"*/BehavCam*/{configuration_file_name}")))
        assert (
            miniscope_config_files
        ), f"The configuration files ({configuration_file_name} files) are missing from '{folder_path}'."

        behavcam_subfolders = list(folder_path.glob("*/BehavCam*/"))
        self._miniscope_config = read_miniscope_config(folder_path=str(behavcam_subfolders[0]))

        self._recording_start_times = get_recording_start_times(folder_path=str(folder_path))
        self._starting_frames = get_starting_frames(folder_path=str(folder_path))
        assert len(self._starting_frames) == len(self._behav_avi_file_paths)
        self._timestamps = get_timestamps(folder_path=str(folder_path), file_pattern="BehavCam*/timeStamps.csv")

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"].update(session_start_time=self._recording_start_times[0])

        metadata["Behavior"]["Device"] = [self._miniscope_config]
        # Add link to Device for ImageSeries
        metadata["Behavior"]["ImageSeries"] = [
            dict(
                name="BehavCamImageSeries",
                device=self._miniscope_config["name"],
                dimension=[self._miniscope_config["ROI"]["width"], self._miniscope_config["ROI"]["height"]],
                unit="px",
            )
        ]

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict,
    ):
        """
        Adds the behavior movies as ImageSeries from provided metadata.
        The created ImageSeries is linked to a Miniscope device.

        Parameters
        ----------
        nwbfile : NWBFile
            The nwbfile to add the image series to.
        metadata : DeepDict
            The metadata storing the necessary metadata for creating the image series and linking it to the appropriate device.
            The metadata for the image series should be stored in metadata["Behavior"]["ImageSeries"].
            The metadata for the device to be linked should be stored in metadata["Behavior"]["Device"].
        """
        from ndx_miniscope.utils import add_miniscope_image_series

        add_miniscope_image_series(
            nwbfile=nwbfile,
            metadata=metadata,
            external_files=[str(file_path) for file_path in self._behav_avi_file_paths],
            starting_frames=self._starting_frames,
            timestamps=self._timestamps,
        )
