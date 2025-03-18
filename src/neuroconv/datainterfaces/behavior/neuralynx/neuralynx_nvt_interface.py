import json
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.behavior import CompassDirection, Position, SpatialSeries

from .nvt_utils import read_data, read_header
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....utils import DeepDict, get_base_schema
from ....utils.json_schema import _NWBMetaDataEncoder
from ....utils.path import infer_path


class NeuralynxNvtInterface(BaseTemporalAlignmentInterface):
    """Data interface for Neuralynx NVT files. NVT files store position tracking information."""

    display_name = "Neuralynx NVT"
    keywords = ("position tracking",)
    associated_suffixes = (".nvt",)
    info = "Interface for writing Neuralynx position tracking .nvt files to NWB."

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = False):
        """
        Interface for writing Neuralynx .nvt files to nwb.

        Parameters
        ----------
        file_path : FilePath
            Path to the .nvt file
        verbose : bool, default: Falsee
            controls verbosity.
        """

        self.file_path = file_path
        self.verbose = verbose
        self._timestamps = self.get_original_timestamps()
        self.header = read_header(self.file_path)
        self.nvt_filename = infer_path(self.header["OriginalFileName"]).name

        super().__init__(file_path=file_path)

    def get_original_timestamps(self) -> np.ndarray:
        data = read_data(self.file_path)

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
        metadata["Behavior"][self.nvt_filename].update(
            position_name="NvtSpatialSeries",
            position_reference_frame="unknown",
            angle_name="NvtAngleSpatialSeries",
            angle_reference_frame="unknown",
        )
        return metadata

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()

        if "Behavior" not in metadata_schema["properties"]:
            metadata_schema["properties"]["Behavior"] = get_base_schema(required=[self.nvt_filename])
            metadata_schema.setdefault("requirements", []).append("Behavior")
        else:
            metadata_schema["properties"]["Behavior"].setdefault("requirements", []).append(self.nvt_filename)

        metadata_schema["properties"]["Behavior"]["properties"].update(
            {
                self.nvt_filename: dict(
                    type="object",
                    required=["position_name", "position_reference_frame"],
                    properties=dict(
                        position_name=dict(type="string", default="NvtSpatialSeries"),
                        position_reference_frame=dict(type="string", default="unknown"),
                        angle_name=dict(type="string", default="NvtAngleSpatialSeries"),
                        angle_reference_frame=dict(type="string", default="unknown"),
                    ),
                )
            }
        )

        return metadata_schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        add_position: bool = True,
        add_angle: Optional[bool] = None,
    ):
        """
        Add NVT data to a given in-memory NWB file

        Parameters
        ----------
        nwbfile : NWBFile
            nwb file to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the nwb file.
        add_position : bool, default=True
        add_angle : bool, optional
            If None, write angle as long as it is not all 0s
        """

        metadata = metadata or self.get_metadata()
        if isinstance(metadata, DeepDict):
            metadata = metadata.to_dict()

        data = read_data(self.file_path)

        if add_position:
            # convert to float and change <= 0 (null) to NaN
            xi = data["Xloc"]
            x = xi.astype(float)
            x[xi <= 0] = np.nan

            yi = data["Yloc"]
            y = yi.astype(float)
            y[yi <= 0] = np.nan

            spatial_series = SpatialSeries(
                name=metadata["Behavior"][self.nvt_filename]["position_name"],
                data=np.c_[x, y],
                reference_frame=metadata["Behavior"][self.nvt_filename]["position_reference_frame"],
                unit="pixels",
                conversion=1.0,
                timestamps=self.get_timestamps(),
                description=f"Pixel x and y coordinates from the .nvt file with header data: {json.dumps(self.header, cls=_NWBMetaDataEncoder)}",
            )

            nwbfile.add_acquisition(Position([spatial_series], name="NvtPosition"))

        if add_angle or (add_angle is None and not np.all(data["Angle"] == 0)):
            nwbfile.add_acquisition(
                CompassDirection(
                    SpatialSeries(
                        name=metadata["Behavior"][self.nvt_filename]["angle_name"],
                        data=data["Angle"],
                        reference_frame=metadata["Behavior"][self.nvt_filename]["angle_reference_frame"],
                        unit="degrees",
                        conversion=1.0,
                        timestamps=spatial_series if add_position else self.get_timestamps(),
                        description=f"Angle from the .nvt file with header data: {json.dumps(self.header, cls=_NWBMetaDataEncoder)}",
                    ),
                    name="NvtCompassDirection",
                )
            )
