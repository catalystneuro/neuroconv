from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import TimeSeries
from pynwb.file import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate


class MiniscopeHeadOrientationInterface(BaseTemporalAlignmentInterface):
    """Data Interface for Miniscope head orientation data from BNO055 IMU sensor."""

    display_name = "Miniscope Head Orientation"
    keywords = ("miniscope", "IMU", "orientation", "quaternion", "BNO055")
    associated_suffixes = (".csv",)
    info = "Interface for Miniscope head orientation data from headOrientation.csv files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the headOrientation.csv file containing quaternion data from BNO055 IMU sensor."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        metadata_key: str = "TimeSeriesMiniscopeHeadOrientation",
        verbose: bool = False,
    ):
        """
        Initialize reading Miniscope head orientation data.

        Parameters
        ----------
        file_path : FilePath
            Path to headOrientation.csv file with columns: Time Stamp (ms), qw, qx, qy, qz
        metadata_key : str, default: 'TimeSeriesMiniscopeHeadOrientation'
            The key in metadata['TimeSeries'] to use for this interface.
        verbose : bool, optional
            If True, enables verbose mode for detailed logging, by default False.
        """
        import pandas as pd

        super().__init__(file_path=file_path, verbose=verbose)
        self.metadata_key = metadata_key
        self._timestamps = None

        # Store the device folder path (parent of headOrientation.csv)
        # This folder contains metaData.json with device info
        self._device_folder_path = Path(file_path).parent

        # Read quaternion data once during initialization
        df = pd.read_csv(file_path)
        self._quaternion_data = df[["qw", "qx", "qy", "qz"]].values

    @staticmethod
    def _get_session_start_time(folder_path):
        """
        Get session start time from the session-level metaData.json file.

        Parameters
        ----------
        folder_path : PathType
            Path to the folder containing the session-level metaData.json file.

        Returns
        -------
        datetime | None
            The session start time if available, None otherwise.
        """
        from roiextractors import MiniscopeImagingExtractor

        return MiniscopeImagingExtractor._get_session_start_time(miniscope_folder_path=folder_path)

    def get_original_timestamps(self) -> np.ndarray:
        """Return the original unaltered timestamps from the CSV file."""
        import pandas as pd

        df = pd.read_csv(self.source_data["file_path"])
        # Read timestamps (in milliseconds) and convert to seconds
        return df["Time Stamp (ms)"].values / 1000.0

    def get_timestamps(self) -> np.ndarray:
        """Return the current timestamps (possibly aligned)."""
        if self._timestamps is None:
            return self.get_original_timestamps()
        return self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """Replace timestamps with aligned version."""
        self._timestamps = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        """Generate metadata for head orientation data."""
        from roiextractors import MiniscopeImagingExtractor

        metadata = super().get_metadata()

        # Read device metadata from metaData.json
        device_metadata_path = self._device_folder_path / "metaData.json"
        device_name = "Miniscope"  # Default
        device_type = None

        if device_metadata_path.exists():
            miniscope_config = MiniscopeImagingExtractor._read_device_folder_metadata(
                metadata_file_path=str(device_metadata_path)
            )
            device_name = miniscope_config.get("deviceName", "Miniscope")
            device_type = miniscope_config.get("deviceType")

        # Build description with device information
        description_parts = [f"Head orientation quaternions (qw, qx, qy, qz) from BNO055 IMU sensor"]
        if device_type:
            description_parts.append(f"on {device_type} device")
        if device_name != "Miniscope":
            description_parts.append(f"({device_name})")
        description = (
            " ".join(description_parts)
            + ". Quaternions represent the rotation from a fixed reference frame to the head-mounted sensor frame. "
            "Quaternion convention: Hamilton (scalar-first: qw, qx, qy, qz)."
        )

        metadata["TimeSeries"] = {
            self.metadata_key: {
                "name": self.metadata_key,
                "description": description,
                "unit": "n.a.",
                "comments": "no comments",
            }
        }

        # Extract session_start_time from parent folder's metaData.json if available
        session_start_time = self._get_session_start_time(folder_path=self._device_folder_path.parent)
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Add head orientation data to NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add head orientation data to.
        metadata : dict, optional
            Metadata dictionary with head orientation configuration.
            Should be of the format::

                metadata['TimeSeries'] = {
                    self.metadata_key: {
                        'name': 'HeadOrientation',
                        'description': 'Head orientation quaternions...',
                        'unit': 'n.a.',
                        'comments': 'Additional information about the data'
                    }
                }

            Where self.metadata_key is used to look up metadata in the metadata dictionary.
        always_write_timestamps : bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
            using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
            explicitly, regardless of whether the sampling rate is uniform.
        """
        # Initialize series_kwargs with data
        series_kwargs = {}
        series_kwargs["data"] = self._quaternion_data

        # Check if timestamps are uniform
        timestamps = self.get_timestamps()
        rate = calculate_regular_series_rate(series=timestamps)  # Returns None if not uniform

        if rate and not always_write_timestamps:
            # Use starting_time and rate for uniform timestamps
            series_kwargs["starting_time"] = float(timestamps[0])
            series_kwargs["rate"] = float(rate)
        else:
            # Write explicit timestamps for non-uniform or when forced
            series_kwargs["timestamps"] = timestamps

        # Update with user-provided metadata
        metadata = metadata if metadata is not None else {}
        timeseries_metadata = metadata.get("TimeSeries", {}).get(self.metadata_key, {})
        series_kwargs.update(timeseries_metadata)

        # Fill missing values with interface defaults
        interface_metadata = self.get_metadata().get("TimeSeries", {}).get(self.metadata_key, {})
        for key, value in interface_metadata.items():
            if key not in series_kwargs:
                series_kwargs[key] = value

        timeseries = TimeSeries(**series_kwargs)

        # Add directly to behavior processing module
        behavior_module = get_module(
            nwbfile=nwbfile,
            name="behavior",
            description="processed behavioral data",
        )
        behavior_module.add(timeseries)
