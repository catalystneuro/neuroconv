from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import DirectoryPath, FilePath
from spikeinterface.core import BaseSorting, BaseSortingSegment

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class XClustSortingSegment(BaseSortingSegment):
    """A single segment of XClust sorting data."""

    def __init__(self, spike_trains: dict):
        super().__init__()
        self._spike_trains = spike_trains

    def get_unit_spike_train(self, unit_id, start_frame, end_frame):
        train = self._spike_trains[unit_id]
        if start_frame is not None:
            train = train[train >= start_frame]
        if end_frame is not None:
            train = train[train < end_frame]
        return train


class XClustSortingExtractor(BaseSorting):
    """A SpikeInterface-compatible sorting extractor for XClust .CEL files.

    This extractor is defined here temporarily and should be moved to SpikeInterface
    once stabilized.

    Each .CEL file represents one cluster (unit). The extractor reads all
    specified .CEL files and creates a single-segment sorting object.

    Parameters
    ----------
    folder_path : str or Path, optional
        Path to a folder containing .CEL files. All .CEL files in the folder will be loaded.
    file_path_list : list of str or Path, optional
        Explicit list of .CEL file paths to load.
    sampling_frequency : float
        The sampling frequency of the original recording in Hz. Required because .CEL files
        do not contain sampling rate information.
    """

    def __init__(
        self,
        *,
        folder_path: Optional[str | Path] = None,
        file_path_list: Optional[list] = None,
        sampling_frequency: float,
    ):
        if folder_path is not None:
            folder_path = Path(folder_path)
            cel_files = sorted(folder_path.glob("*.CEL"))
            if not cel_files:
                raise FileNotFoundError(f"No .CEL files found in {folder_path}")
        else:
            cel_files = [Path(f) for f in file_path_list]

        # Parse all files, using the file stem as unit ID for uniqueness
        unit_ids = []
        cluster_ids = []
        spike_trains = {}
        for file_path in cel_files:
            cluster_id, spike_times_seconds = self._parse_cel_file(file_path)
            unit_id = file_path.stem
            unit_ids.append(unit_id)
            cluster_ids.append(cluster_id)
            spike_frames = np.round(spike_times_seconds * sampling_frequency).astype(np.int64)
            spike_trains[unit_id] = np.sort(spike_frames)

        super().__init__(sampling_frequency=sampling_frequency, unit_ids=unit_ids)

        self.set_property(key="cluster_id", values=cluster_ids)

        segment = XClustSortingSegment(spike_trains=spike_trains)
        self.add_sorting_segment(segment)

    @staticmethod
    def _parse_cel_file(file_path: str | Path) -> tuple:
        """Parse a single .CEL file, returning cluster_id and spike_times array.

        Parameters
        ----------
        file_path : str or Path
            Path to the .CEL file.

        Returns
        -------
        cluster_id : str
            The cluster ID from the header.
        spike_times_seconds : np.ndarray
            Array of spike times in seconds.
        """
        file_path = Path(file_path)
        text = file_path.read_text(encoding="ascii", errors="replace")
        lines = text.splitlines()

        # Parse header
        cluster_id = None
        end_header_line = None
        for index, line in enumerate(lines):
            if line.startswith("%%ENDHEADER"):
                end_header_line = index
                break
            if line.startswith("% Cluster:"):
                cluster_id = line.split(":")[-1].strip()

        if end_header_line is None:
            raise ValueError(f"Could not find %%ENDHEADER in {file_path}")
        if cluster_id is None:
            raise ValueError(f"Could not find Cluster ID in header of {file_path}")

        # Find the Fields line to get time column index
        fields_line = None
        for line in lines:
            if line.startswith("% Fields:"):
                fields_line = line
                break

        if fields_line is None:
            raise ValueError(f"Could not find Fields line in header of {file_path}")

        # Parse field names (after "% Fields:" prefix)
        fields_str = fields_line.split(":", 1)[1]
        field_names = fields_str.split()
        time_col_index = field_names.index("time")

        # Parse data rows after header
        data_lines = lines[end_header_line + 1 :]
        spike_times = []
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            values = line.split()
            spike_times.append(float(values[time_col_index]))

        spike_times_seconds = np.array(spike_times, dtype=np.float64)
        return cluster_id, spike_times_seconds


class XClustSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting XClust (.CEL) spike sorting data."""

    display_name = "XClust Sorting"
    associated_suffixes = (".CEL",)
    info = "Interface for XClust (.CEL) spike sorting data."

    @classmethod
    def get_extractor_class(cls):
        return XClustSortingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"] = {
            "folder_path": {
                "type": "string",
                "format": "directory",
                "description": "Path to folder containing .CEL files.",
            },
            "file_path_list": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of paths to .CEL files.",
            },
            "sampling_frequency": {
                "type": "number",
                "description": "Sampling frequency of the original recording in Hz.",
            },
        }
        source_schema["required"] = ["sampling_frequency"]
        return source_schema

    def __init__(
        self,
        *,
        folder_path: Optional[DirectoryPath] = None,
        file_path_list: Optional[list[FilePath]] = None,
        sampling_frequency: float,
        verbose: bool = False,
    ):
        """
        Initialize the XClust sorting interface.

        Parameters
        ----------
        folder_path : DirectoryPath, optional
            Path to a folder containing .CEL files.
        file_path_list : list of FilePath, optional
            Explicit list of .CEL file paths.
        sampling_frequency : float
            Sampling frequency of the original recording in Hz.
        verbose : bool, default: False
            Whether to print verbose output.
        """
        if folder_path is not None and file_path_list is not None:
            raise ValueError("Specify either 'folder_path' or 'file_path_list', not both.")
        if folder_path is None and file_path_list is None:
            raise ValueError("Must specify either 'folder_path' or 'file_path_list'.")

        if file_path_list is not None:
            file_path_list = [str(p) for p in file_path_list]

        super().__init__(
            verbose=verbose,
            folder_path=folder_path,
            file_path_list=file_path_list,
            sampling_frequency=sampling_frequency,
        )
