from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, dict_deep_update


class MiniscopeImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MiniscopeImagingExtractor."""

    display_name = "Miniscope Imaging"
    associated_suffixes = (".avi", ".csv", ".json")
    info = "Interface for Miniscope imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The main Miniscope folder. The microscope movie files are expected to be in sub folders within the main folder."

        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath):
        """
        Initialize reading the Miniscope imaging data.

        Parameters
        ----------
        folder_path : DirectoryPath
            The main Miniscope folder.
            The microscope movie files are expected to be in sub folders within the main folder.
        """
        from ndx_miniscope.utils import get_recording_start_times, read_miniscope_config

        miniscope_folder_paths = list(Path(folder_path).rglob("Miniscope"))
        assert miniscope_folder_paths, "The main folder should contain at least one subfolder named 'Miniscope'."

        super().__init__(folder_path=folder_path)

        self._miniscope_config = read_miniscope_config(folder_path=str(miniscope_folder_paths[0]))
        self._recording_start_times = get_recording_start_times(folder_path=folder_path)
        self.photon_series_type = "OnePhotonSeries"

    def get_metadata(self) -> DeepDict:
        from ....tools.roiextractors import get_nwb_imaging_metadata

        metadata = super().get_metadata()
        default_metadata = get_nwb_imaging_metadata(self.imaging_extractor, photon_series_type=self.photon_series_type)
        metadata = dict_deep_update(metadata, default_metadata)
        metadata["Ophys"].pop("TwoPhotonSeries", None)

        metadata["NWBFile"].update(session_start_time=self._recording_start_times[0])

        device_metadata = metadata["Ophys"]["Device"][0]
        miniscope_config = deepcopy(self._miniscope_config)
        device_name = miniscope_config.pop("name")
        device_metadata.update(name=device_name, **miniscope_config)
        # Add link to Device for ImagingPlane
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
        one_photon_series_metadata.update(unit="px")

        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"]["definitions"]["Device"]["additionalProperties"] = True
        return metadata_schema

    def get_original_timestamps(self) -> np.ndarray:
        from ndx_miniscope.utils import get_timestamps

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
        from ndx_miniscope.utils import add_miniscope_device

        from ....tools.roiextractors import add_photon_series_to_nwbfile

        miniscope_timestamps = self.get_original_timestamps()
        imaging_extractor = self.imaging_extractor

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_frames()])
            imaging_extractor = self.imaging_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
            miniscope_timestamps = miniscope_timestamps[:stub_frames]

        imaging_extractor.set_times(times=miniscope_timestamps)

        device_metadata = metadata["Ophys"]["Device"][0]
        add_miniscope_device(nwbfile=nwbfile, device_metadata=device_metadata)

        add_photon_series_to_nwbfile(
            imaging=imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
        )
