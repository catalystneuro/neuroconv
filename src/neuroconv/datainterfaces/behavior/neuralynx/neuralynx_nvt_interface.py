import json
from typing import Optional

import numpy as np
from pynwb import NWBFile
from pynwb.behavior import SpatialSeries, Position, CompassDirection

from .read_nvt import read_nvt, parse_header
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....utils import FilePathType, DeepDict


class NeuralynxNvtInterface(BaseTemporalAlignmentInterface):
    """Data interface for Neuralynx NVT files."""

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Interface for writing Neuralynx .nvt files to nwb.

        Parameters
        ----------
        file_path : FilePathType
            Path to the .nvt file
        verbose : bool, default: True
            controls verbosity.
        """

        self.file_path = file_path
        self.verbose = verbose
        self._timestamps = self.get_original_timestamps()
        self.header = parse_header(self.file_path)
        super().__init__(file_path=file_path)

    def get_original_timestamps(self) -> np.ndarray:
        data = read_nvt(self.file_path)

        times = data["TimeStamp"] / 1000000  # Neuralynx stores times in microseconds
        times = times - times[0]

        return times

    def get_timestamps(self) -> np.ndarray:
        return self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["NWBFile"].update(session_start_time=self.header["TimeCreated"])
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        add_position=True,
        add_angle=True,
    ):
        """
        Conversion from NVT to NWB

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict, optional
            metadata info for constructing the nwb file.
        add_position: bool, default=True
        add_angle: bool, default=True
        """

        data = read_nvt(self.file_path)

        xi = data["Xloc"]
        x = xi.astype(float)
        x[xi <= 0] = np.nan

        yi = data["Yloc"]
        y = yi.astype(float)
        y[yi <= 0] = np.nan

        if add_position:
            nwbfile.add_acquisition(
                Position(
                    SpatialSeries(
                        name="NvtPositionSpatialSeries",
                        data=np.c_[x, y],
                        reference_frame="unknown",
                        unit="pixels",
                        conversion=1.0,
                        timestamps=self.get_timestamps(),
                        description=f"Pixel x and y coordinates from the .nvt file with header data: {json.dumps(self.header)}"
                    ),
                    name="NvtPosition",
                )
            )

        if add_angle:
            nwbfile.add_acquisition(
                CompassDirection(
                    SpatialSeries(
                        name="NvtAngleSpatialSeries",
                        data=data["Angle"],
                        reference_frame="unknown",
                        unit="pixels",
                        conversion=1.0,
                        timestamps=self.get_timestamps(),
                        description=f"Angle from the .nvt file with header data: {json.dumps(self.header)}"
                    ),
                    name="NvtCompassDirection",
                )
            )


