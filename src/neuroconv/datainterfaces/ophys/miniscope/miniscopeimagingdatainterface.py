from copy import deepcopy
from typing import Optional

import numpy as np
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ..miniscope import add_miniscope_device, get_recording_start_times, get_timestamps
from ....tools.nwb_helpers import make_or_load_nwbfile
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

        self._recording_start_times = get_recording_start_times(folder_path=folder_path)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        metadata["NWBFile"].update(session_start_time=self._recording_start_times[0])

        miniscope_config = deepcopy(self.imaging_extractor._miniscope_config)
        miniscope_config.pop("deviceDirectory")
        miniscope_config.pop("deviceID")
        device_name = miniscope_config.pop("deviceName")

        metadata["Ophys"]["Device"][0].update(name=device_name, **miniscope_config)
        metadata["Ophys"]["ImagingPlane"][0].update(
            device=device_name,
        )

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        timestamps = get_timestamps(folder_path=self.source_data["folder_path"])
        return np.array(timestamps)

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        verbose: bool = True,
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

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=verbose,
        ) as nwbfile_out:
            add_miniscope_device(nwbfile=nwbfile_out, metadata=metadata)

            add_photon_series(
                imaging=imaging_extractor,
                nwbfile=nwbfile_out,
                metadata=metadata,
                photon_series_type="OnePhotonSeries",
            )
