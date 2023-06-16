from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from ndx_miniscope.utils import (
    add_miniscope_device,
    get_recording_start_times,
    get_timestamps,
    read_miniscope_config,
)
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....tools.roiextractors.roiextractors import add_photon_series
from ....utils import DeepDict, FolderPathType


class MiniscopeImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MiniscopeImagingExtractor."""

    def __init__(self, folder_path: FolderPathType):
        """
        Initialize reading Miniscope format.

        Parameters
        ----------
        folder_path : FolderPathType
            path to the folder containing the Miniscope files.
        """

        super().__init__(folder_path=folder_path)

        miniscope_subfolders = list(Path(folder_path).glob(f"*/Miniscope/"))
        self._miniscope_config = read_miniscope_config(folder_path=str(miniscope_subfolders[0]))

        self._recording_start_times = get_recording_start_times(folder_path=folder_path)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        metadata["NWBFile"].update(session_start_time=self._recording_start_times[0])

        device_metadata = metadata["Ophys"]["Device"][0]
        miniscope_config = deepcopy(self._miniscope_config)
        device_name = miniscope_config.pop("name")
        device_metadata.update(name=device_name, **miniscope_config)
        # Add link to Device for ImagingPlane
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(device=device_name)

        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"]["properties"]["definitions"]["Device"]["additionalProperties"] = True
        return metadata_schema

    def get_original_timestamps(self) -> np.ndarray:
        timestamps = get_timestamps(folder_path=self.source_data["folder_path"])
        return np.array(timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "OnePhotonSeries",
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        miniscope_timestamps = self.get_original_timestamps()
        imaging_extractor = self.imaging_extractor

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_frames()])
            imaging_extractor = self.imaging_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
            miniscope_timestamps = miniscope_timestamps[:stub_frames]

        imaging_extractor.set_times(times=miniscope_timestamps)

        device_metadata = metadata["Ophys"]["Device"][0]
        add_miniscope_device(nwbfile=nwbfile, device_metadata=device_metadata)

        add_photon_series(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
        )
