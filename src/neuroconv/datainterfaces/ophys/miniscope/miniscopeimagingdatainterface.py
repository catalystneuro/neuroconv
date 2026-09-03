import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ._miniscope_readers import (
    _config_to_miniscope_device_metadata,
    _config_to_miniscope_device_model_metadata,
)
from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, dict_deep_update, to_snake_case


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

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import MiniscopeMultiRecordingImagingExtractor

        return MiniscopeMultiRecordingImagingExtractor

    @validate_call
    def __init__(
        self, folder_path: DirectoryPath, *args, verbose: bool = False
    ):  # TODO: change to * (keyword only) on or after August 2026
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
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to _MiniscopeMultiRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)

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

        metadata = super().get_metadata(use_new_metadata_format=False)
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

    def _get_metadata_schema_for_old_list_format(self) -> dict:
        """
        Get the old list-based metadata schema for the Miniscope imaging data.

        Returns
        -------
        dict
            The schema dictionary containing metadata definitions and requirements
            for the Miniscope imaging interface.
        """
        metadata_schema = super()._get_metadata_schema_for_old_list_format()
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
        *,
        photon_series_index: int = 0,  # Ignore, here for backwards compatibility
        stub_samples: int = 100,
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
            If True, only a subset of the data (defined by `stub_samples`) will be added for testing purposes,
            by default False.
        stub_samples : int, default: 100
            The number of samples (frames) to include if `stub_test` is True.
        """
        from ndx_miniscope.utils import add_miniscope_device

        from ....tools.roiextractors.roiextractors_pending_deprecation import (
            _add_photon_series_to_nwbfile_old_list_format,
        )

        miniscope_timestamps = self.get_original_timestamps()
        imaging_extractor = self.imaging_extractor
        if stub_test:
            stub_samples = min([stub_samples, self.imaging_extractor.get_num_samples()])
            imaging_extractor = self.imaging_extractor.slice_samples(start_sample=0, end_sample=stub_samples)
            miniscope_timestamps = miniscope_timestamps[:stub_samples]

        imaging_extractor.set_times(times=miniscope_timestamps)

        device_metadata = metadata["Ophys"]["Device"][0]
        add_miniscope_device(nwbfile=nwbfile, device_metadata=device_metadata)

        _add_photon_series_to_nwbfile_old_list_format(
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
    2. file_paths: For non-standard folder structures with custom organization
    """

    display_name = "Miniscope Imaging"
    associated_suffixes = (".avi", ".csv", ".json")
    info = "Interface for Miniscope imaging data from single recordings."
    ExtractorName = "MiniscopeImagingExtractor"

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import MiniscopeImagingExtractor

        return MiniscopeImagingExtractor

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
        *,
        file_paths: list = None,
        timeStamps_file_path: str = None,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """
        Initialize reading the Miniscope imaging data.

        Two usage modes are supported:
        - Provide only folder_path for standard folder structures
        - Provide file_paths for custom folder structures
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
                └── timeStamps.csv         # required timestamps file
        file_paths : list, optional
            List of .avi file paths to be processed. These files should be from the same
            recording session and must follow the naming convention (0.avi, 1.avi, 2.avi, ...).
            Files will be concatenated in numerical order.
            Use this for non-standard folder structures.
        timeStamps_file_path : str, optional
            Path to the timeStamps.csv file containing timestamps relative to the recording start.
            If not provided, the extractor will look for timeStamps.csv in the same directory
            as the video files.
        verbose : bool, optional
            If True, enables verbose mode for detailed logging, by default False.
        metadata_key : str, optional
            # TODO: improve docstring once #1653 (ophys metadata documentation) is merged
            Metadata key for this interface. When None, defaults to "miniscope_imaging".
        """
        if folder_path is None and file_paths is None:
            raise ValueError("Either 'folder_path' or 'file_paths' must be provided.")

        from ._miniscope_readers import _raise_if_miniscope_v3_format

        if folder_path is not None:
            _raise_if_miniscope_v3_format(folder_path=str(folder_path))
        elif file_paths is not None:
            _raise_if_miniscope_v3_format(folder_path=str(Path(file_paths[0]).parent))

        if folder_path is not None and file_paths is not None:
            raise ValueError("When 'folder_path' is provided, 'file_paths' cannot be specified.")

        # Store the device folder path for metadata extraction
        # The device folder contains metaData.json and .avi files
        if folder_path is not None:
            self._device_folder_path = Path(folder_path)
        elif file_paths is not None:
            # Infer from file_paths - all .avi files should be in the same folder
            self._device_folder_path = Path(file_paths[0]).parent
        else:
            self._device_folder_path = None

        if metadata_key is None:
            metadata_key = "miniscope_imaging"

        # Initialize with the provided parameters
        super().__init__(
            folder_path=folder_path,
            file_paths=file_paths,
            timestamps_path=timeStamps_file_path,
            verbose=verbose,
            metadata_key=metadata_key,
        )

        self.photon_series_type = "OnePhotonSeries"

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

    @property
    def device_metadata_key(self) -> str:
        """The ``metadata["Devices"]`` key this recording's Miniscope is registered under.

        Keyed by the Miniscope rather than by the per-interface ``metadata_key``, because their
        cardinalities differ: one Miniscope recorded over several sessions is one device but one series
        per session, and registering one device name under several keys is rejected. Reading it off the
        device is also what lets a converter's interfaces agree on the entry without being told.
        """
        return to_snake_case(self._read_device_name())

    def _read_device_name(self) -> str:
        """Return the ``deviceName`` of this recording's device folder, or the default."""
        from roiextractors import MiniscopeImagingExtractor

        device_metadata_path = self._device_folder_path / "metaData.json"
        if not device_metadata_path.exists():
            return "Miniscope"

        miniscope_config = MiniscopeImagingExtractor._read_device_folder_metadata(
            metadata_file_path=str(device_metadata_path)
        )
        return miniscope_config.get("deviceName", "Miniscope")

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        """Get metadata with device information from Miniscope configuration.

        Parameters
        ----------
        use_new_metadata_format : bool, default: True
            When False, returns the old list-based metadata format (backward compatible).
            When True, returns dict-based metadata keyed by ``metadata_key`` under
            ``Devices``, ``Ophys.ImagingPlanes``, and ``Ophys.MicroscopySeries``.
        """
        from roiextractors import MiniscopeImagingExtractor

        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)

        # Read device metadata from metaData.json using the extractor's static method
        device_metadata_path = self._device_folder_path / "metaData.json"

        device_name = "Miniscope"  # Default
        model_name = None
        miniscope_config = None
        if device_metadata_path.exists():
            miniscope_config = MiniscopeImagingExtractor._read_device_folder_metadata(
                metadata_file_path=str(device_metadata_path)
            )
            device_name = miniscope_config.get("deviceName", "Miniscope")
            if "deviceType" in miniscope_config:
                model_name = miniscope_config["deviceType"]

        # Extract session_start_time from parent folder's metaData.json if available
        # The parent folder of the device folder contains the session-level metaData.json
        session_start_time = self._get_session_start_time(folder_path=self._device_folder_path.parent)
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        if use_new_metadata_format:
            device_metadata_key = self.device_metadata_key
            # The whole device configuration reaches the Miniscope device, which the registry builds
            # from the 'type' field; nothing here is written by hand.
            if miniscope_config is not None:
                device_entry = _config_to_miniscope_device_metadata(
                    miniscope_config={**miniscope_config, "name": device_name}
                )
                # The model is keyed by the hardware design it names, since every Miniscope of that
                # design shares it, and is linked from the device the way pynwb 4 asks for.
                model_entry = _config_to_miniscope_device_model_metadata(miniscope_config=miniscope_config)
                if model_entry is not None:
                    device_model_metadata_key = to_snake_case(model_entry["name"])
                    device_entry["device_model_metadata_key"] = device_model_metadata_key
                    metadata["DeviceModels"] = {device_model_metadata_key: model_entry}
            else:
                device_entry = {"type": "Miniscope", "name": device_name}
            metadata["Devices"] = {device_metadata_key: device_entry}
            metadata["Ophys"] = {
                "ImagingPlanes": {
                    self.metadata_key: {
                        "name": "ImagingPlane",
                        "device_metadata_key": device_metadata_key,
                        "imaging_rate": self.imaging_extractor.get_sampling_frequency(),
                    },
                },
                "MicroscopySeries": {
                    self.metadata_key: {
                        "name": "OnePhotonSeries",
                        "unit": "px",
                        "imaging_plane_metadata_key": self.metadata_key,
                        "description": "Imaging data acquired with a Miniscope.",
                    },
                },
            }
            return metadata

        # Old list-based path
        device_metadata = metadata["Ophys"]["Device"][0]
        device_updates = {"name": device_name}
        if model_name is not None:
            device_updates["model_name"] = model_name
        device_metadata.update(device_updates)

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        if "OnePhotonSeries" in metadata["Ophys"]:
            one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
            one_photon_series_metadata.update(unit="px")

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "OnePhotonSeries",
        **kwargs,
    ):
        """
        Add imaging data to the NWBFile with Miniscope-specific device.

        This method adds the Miniscope device and then delegates to the parent class.
        """
        from ....tools.roiextractors.roiextractors import _is_dict_based_metadata

        if not _is_dict_based_metadata(metadata if metadata is not None else self.get_metadata()):
            # Old list-based path: the device is not in the registry, so it is written here.
            from ndx_miniscope.utils import add_miniscope_device

            add_miniscope_device(nwbfile=nwbfile, device_metadata=metadata["Ophys"]["Device"][0])

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            **kwargs,
        )
