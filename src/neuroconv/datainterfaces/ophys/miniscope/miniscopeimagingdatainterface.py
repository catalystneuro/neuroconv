from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, dict_deep_update


class _MiniscopeMultiRecordingInterface(BaseImagingExtractorInterface):
    """Data Interface for MiniscopeMultiRecordingImagingExtractor."""

    display_name = "Miniscope Multi-Recording Imaging"
    associated_suffixes = (".avi", ".csv", ".json")
    info = "Interface for Miniscope multi-recording imaging data."
    ExtractorName = "MiniscopeMultiRecordingImagingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Miniscope imaging interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the Miniscope imaging interface.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The main Miniscope folder. The microscope movie files are expected to be in sub folders within the main folder."

        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        """
        Initialize reading the Miniscope imaging data.

        Parameters
        ----------
        folder_path : DirectoryPath
            The main Miniscope folder.
            The microscope movie files are expected to be in sub folders within the main folder.
        verbose : bool, optional
            If True, enables verbose mode for detailed logging, by default False.
        """
        from ndx_miniscope.utils import get_recording_start_times, read_miniscope_config

        miniscope_folder_paths = list(Path(folder_path).rglob("Miniscope"))
        assert miniscope_folder_paths, "The main folder should contain at least one subfolder named 'Miniscope'."

        super().__init__(folder_path=folder_path, verbose=verbose)

        self._miniscope_config = read_miniscope_config(folder_path=str(miniscope_folder_paths[0]))
        self._recording_start_times = get_recording_start_times(folder_path=folder_path)
        self.photon_series_type = "OnePhotonSeries"

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Miniscope imaging data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            and one-photon series configuration.
        """
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
        """
        Get the metadata schema for the Miniscope imaging data.

        Returns
        -------
        dict
            The schema dictionary containing metadata definitions and requirements
            for the Miniscope imaging interface.
        """
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
        metadata: dict | None = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "OnePhotonSeries",
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        """
        Add imaging data to the specified NWBFile, including device and photon series information.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the imaging data will be added.
        metadata : dict, optional
            Metadata containing information about the imaging device and photon series. If None, default metadata is used.
        photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
            The type of photon series to be added, either "TwoPhotonSeries" or "OnePhotonSeries", by default "OnePhotonSeries".
        stub_test : bool, optional
            If True, only a subset of the data (defined by `stub_frames`) will be added for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include if `stub_test` is True, by default 100.
        """
        from ndx_miniscope.utils import add_miniscope_device

        from ....tools.roiextractors import add_photon_series_to_nwbfile

        miniscope_timestamps = self.get_original_timestamps()
        imaging_extractor = self.imaging_extractor

        if stub_test:
            stub_frames = min([stub_frames, self.imaging_extractor.get_num_samples()])
            imaging_extractor = self.imaging_extractor.slice_samples(start_sample=0, end_sample=stub_frames)
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


class MiniscopeImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MiniscopeImagingExtractor.

    This interface handles single Miniscope recordings from a folder containing .avi files
    and a metaData.json configuration file. It provides two usage modes:

    1. folder_path: For standard folder structures where files follow the expected naming convention
    2. file_paths + configuration_file_path: For non-standard folder structures with custom organization
    """

    display_name = "Miniscope Imaging"
    associated_suffixes = (".avi", ".csv", ".json")
    info = "Interface for Miniscope imaging data from single recordings."
    ExtractorName = "MiniscopeImagingExtractor"

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """
        Map interface parameters to extractor parameters.

        The interface uses timeStamps_file_path but the extractor expects timestamps_path.
        """
        extractor_kwargs = source_data.copy()

        # Map timeStamps_file_path to timestamps_path for the extractor
        if "timeStamps_file_path" in extractor_kwargs:
            extractor_kwargs["timestamps_path"] = extractor_kwargs.pop("timeStamps_file_path")

        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath = None,
        file_paths: list = None,
        configuration_file_path: str = None,
        timeStamps_file_path: str = None,
        verbose: bool = False,
    ):
        """
        Initialize reading the Miniscope imaging data.

        Two usage modes are supported:
        - Provide only folder_path for standard folder structures
        - Provide file_paths and configuration_file_path for custom folder structures
        These modes are mutually exclusive.

        Parameters
        ----------
        folder_path : DirectoryPath, optional
            Path to the Miniscope folder containing .avi files and metaData.json (required).
            Use this for standard single-recording folder structures.
            Expected folder structure:

            .. code-block::

                folder_path/
                ├── 0.avi                  # video file 1
                ├── 1.avi                  # video file 2
                ├── 2.avi                  # video file 3
                ├── ...                    # additional video files
                ├── metaData.json          # required configuration file
                └── timeStamps.csv         # optional timestamps file
        file_paths : list, optional
            List of .avi file paths to be processed. These files should be from the same
            recording session and must follow the naming convention (0.avi, 1.avi, 2.avi, ...).
            Files will be concatenated in numerical order.
            Use this for non-standard folder structures.
        configuration_file_path : str, optional
            Path to the metaData.json configuration file containing recording parameters.
            Required when using file_paths parameter.
        timeStamps_file_path : str, optional
            Path to the timeStamps.csv file containing timestamps relative to the recording start.
            If not provided, the extractor will look for timeStamps.csv in the parent directory
            of the configuration file. If the file is not found,
            timestamps will be generated as regular intervals based on the sampling frequency
            from the configuration file, starting at 0.
        verbose : bool, optional
            If True, enables verbose mode for detailed logging, by default False.
        """
        if folder_path is None and (file_paths is None or configuration_file_path is None):
            raise ValueError(
                "Either 'folder_path' must be provided, or both 'file_paths' and 'configuration_file_path' must be provided."
            )

        if folder_path is not None and (file_paths is not None or configuration_file_path is not None):
            raise ValueError(
                "When 'folder_path' is provided, 'file_paths' and 'configuration_file_path' cannot be specified. "
                "Use either folder_path alone or provide file_paths with configuration_file_path."
            )

        # Initialize with the provided parameters
        super().__init__(
            folder_path=folder_path,
            file_paths=file_paths,
            configuration_file_path=configuration_file_path,
            timestamps_path=timeStamps_file_path,
            verbose=verbose,
        )

        self.photon_series_type = "OnePhotonSeries"

    def get_metadata(self) -> dict:
        """Get metadata with device information from Miniscope configuration."""
        from pathlib import Path

        metadata = super().get_metadata()

        # Extract device metadata from the extractor's config
        device_metadata = metadata["Ophys"]["Device"][0]
        device_name = self.imaging_extractor._miniscope_config.get("deviceName", "Miniscope")

        # Only include valid Device schema fields
        device_updates = {"name": device_name}

        # Map deviceType to model_name if available
        if "deviceType" in self.imaging_extractor._miniscope_config:
            device_updates["model_name"] = self.imaging_extractor._miniscope_config["deviceType"]

        device_metadata.update(device_updates)

        # Update imaging plane metadata
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        # Update photon series metadata
        if "OnePhotonSeries" in metadata["Ophys"]:
            one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
            one_photon_series_metadata.update(unit="px")

        # Extract session_start_time from parent folder's metaData.json if available
        # The parent folder of the Miniscope folder may contain the recording session metaData.json
        miniscope_folder = Path(self.imaging_extractor._miniscope_folder_path)
        parent_metadata_path = miniscope_folder.parent / "metaData.json"

        if parent_metadata_path.exists():
            from roiextractors.extractors.miniscopeimagingextractor.miniscope_utils import (
                get_recording_start_time,
            )

            try:
                session_start_time = get_recording_start_time(file_path=str(parent_metadata_path))
                metadata["NWBFile"]["session_start_time"] = session_start_time
            except KeyError:
                # metaData.json exists but doesn't have required recording start time fields
                pass

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "OnePhotonSeries",
        **kwargs,
    ):
        """
        Add imaging data to the NWBFile with Miniscope-specific device.

        This method adds the Miniscope device and then delegates to the parent class.
        """
        from ndx_miniscope.utils import add_miniscope_device

        # Add Miniscope device - required for proper ndx_miniscope.Miniscope device type
        device_metadata = metadata["Ophys"]["Device"][0]
        add_miniscope_device(nwbfile=nwbfile, device_metadata=device_metadata)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            **kwargs,
        )
