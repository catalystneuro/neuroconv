from __future__ import annotations

import json
import warnings
from pathlib import Path

from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from .miniscopeimagingdatainterface import (
    MiniscopeImagingInterface,
    _MiniscopeMultiRecordingInterface,
)
from ... import MiniscopeBehaviorInterface, MiniscopeHeadOrientationInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature
from ....utils.str_utils import to_camel_case


class MiniscopeConverter(ConverterPipe):
    """Bundle Miniscope imaging and optional behavior recordings into a single NWB conversion."""

    display_name = "Miniscope Imaging and Video"
    keywords = (
        MiniscopeImagingInterface.keywords
        + MiniscopeBehaviorInterface.keywords
        + MiniscopeHeadOrientationInterface.keywords
    )
    associated_suffixes = (
        MiniscopeImagingInterface.associated_suffixes
        + MiniscopeBehaviorInterface.associated_suffixes
        + MiniscopeHeadOrientationInterface.associated_suffixes
    )
    info = "Converter for handling both imaging and video recordings from Miniscope."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_json_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"]["description"] = "The path to the main Miniscope folder."
        source_schema["properties"]["user_configuration_file_path"] = {
            "type": "string",
            "format": "file-path",
            "description": (
                "Path to the Miniscope acquisition User Config JSON file (named 'UserConfigFile.json' in the Miniscope"
                " documentation and source code). When provided, the converter uses this configuration to interpret the"
                " folder hierarchy and device names instead of relying on a fixed directory structure."
            ),
            "default": None,
        }
        return source_schema

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        user_configuration_file_path: FilePath | None = None,
        verbose: bool = False,
    ):
        """Instantiate Miniscope imaging (and optional behavior) interfaces.

        Parameters
        ----------
        folder_path : DirectoryPath
            **Root data directory** containing the Miniscope acquisition data. This should be the base directory
            where the configured directory structure sits (e.g. "dataDirectory" in the User Config).

            - With config file: The top-level directory containing the hierarchy defined by 'directoryStructure'
            - Without config file (legacy): The directory containing timestamp subfolders with Miniscope/ folders

            IMPORTANT: The 'dataDirectory' field in the User Config file is ignored. Always pass the actual
            data root directory as folder_path.
        user_configuration_file_path : FilePath, optional
            Path to the Miniscope "User Config" JSON file (the Miniscope documentation and source code refer to
            this artifact as ``UserConfigFile.json``). When provided, the converter uses the configuration to
            discover Miniscope device folders and session hierarchy, supporting multiple simultaneous Miniscopes
            and custom directory layouts. If omitted, the converter falls back to the legacy layout (see Notes).
        verbose : bool, default: False
            Controls verbosity.

        Notes
        -----
        The Miniscope acquisition software saves a "User Config" JSON that includes:

        - ``dataDirectory`` and ``directoryStructure``: ordered keys (e.g., researcher, experiment, animal,
          date, time) used to build the on-disk folder hierarchy.
        - ``devices[miniscopes]``: mapping of Miniscope device names (e.g., ``"ACC_miniscope2"``) to their
          acquisition parameters.

        Example 1 - Dual Miniscope with 5-level hierarchy::

            {
                "dataDirectory": "./dual_miniscope_data",
                "directoryStructure": [
                    "researcherName",
                    "experimentName",
                    "animalName",
                    "date",
                    "time"
                ],
                "researcherName": "researcher_name",
                "experimentName": "experiment_name",
                "animalName": "animal_name",
                "devices": {
                    "miniscopes": {
                        "ACC_miniscope2": {...},
                        "HPC_miniscope1": {...}
                    }
                }
            }

        This produces a folder tree such as::

            dual_miniscope_data/
            ├── researcher_name/
            │   └── experiment_name/
            │       └── animal_name/
            │           └── 2025_06_12/
            │               ├── 15_15_04/
            │               │   ├── ACC_miniscope2/
            │               │   │   ├── 0.avi
            │               │   │   ├── 1.avi
            │               │   │   ├── 2.avi
            │               │   │   ├── metaData.json
            │               │   │   └── timeStamps.csv
            │               │   ├── HPC_miniscope1/
            │               │   │   ├── 0.avi
            │               │   │   ├── 1.avi
            │               │   │   ├── 2.avi
            │               │   │   ├── metaData.json
            │               │   │   └── timeStamps.csv
            │               │   └── metaData.json
            │               └── 15_26_31/
            │                   ├── ACC_miniscope2/
            │                   │   ├── 0.avi
            │                   │   ├── 1.avi
            │                   │   ├── metaData.json
            │                   │   └── timeStamps.csv
            │                   ├── HPC_miniscope1/
            │                   │   ├── 0.avi
            │                   │   ├── 1.avi
            │                   │   ├── metaData.json
            │                   │   └── timeStamps.csv
            │                   └── metaData.json

        Example 2 - Single Miniscope with 3-level hierarchy::

            {
                "dataDirectory": "./miniscope_recordings",
                "directoryStructure": [
                    "animalName",
                    "date",
                    "time"
                ],
                "animalName": "mouse_001",
                "devices": {
                    "miniscopes": {
                        "Miniscope": {...}
                    }
                }
            }

        Which yields::

            miniscope_recordings/
            └── mouse_001/
                └── 2022_09_19/
                    └── 09_18_41/
                        ├── Miniscope/
                        │   ├── 0.avi
                        │   ├── 1.avi
                        │   ├── 2.avi
                        │   ├── metaData.json
                        │   └── timeStamps.csv
                        └── metaData.json

        The converter walks the directory structure, creating one imaging interface per Miniscope device and
        preserving their individual timestamps. Behavior video is added only if ``BehavCam_`` folders (with
        metadata) are present. For devices recorded multiple times, each timestamp folder is instantiated as a
        separate interface labeled ``SegmentXX`` (with zero padding based on the total number of segments) so
        repeated recordings remain distinct while sharing a common device definition.

        **Backwards compatibility:** If ``user_configuration_file_path`` is not provided, the converter falls back to the
        original "Tye Lab" layout that expects timestamp subfolders with ``Miniscope/`` and optional ``BehavCam_*/``
        directories (each holding their own ``metaData.json`` and ``timeStamps.csv`` files)::

            main_folder/
            ├── timestamp_one/
            │   ├── Miniscope/
            │   │   ├── 0.avi
            │   │   ├── 1.avi
            │   │   ├── metaData.json
            │   │   └── timeStamps.csv
            │   ├── BehavCam_*/
            │   │   ├── 0.avi
            │   │   ├── metaData.json
            │   │   └── timeStamps.csv
            │   └── metaData.json
            └── timestamp_two/
                └── ...

        Use the configuration file whenever possible to describe other layouts explicitly.
        """
        self.verbose = verbose
        self._folder_path = Path(folder_path)
        self.data_interface_objects: dict[str, object] = {}
        self._user_configuration_file_path = user_configuration_file_path

        data_interfaces = {}
        if self._user_configuration_file_path is not None:
            # Load user configuration
            config_path = Path(self._user_configuration_file_path)
            with config_path.open() as f:
                self._user_config = json.load(f)

            data_directory_path_in_config = self._user_config.get("dataDirectory", "")
            data_directory_name_in_json = data_directory_path_in_config.split("/")[-1]
            if data_directory_name_in_json != self._folder_path.name:
                warnings.warn(
                    f"Ignoring 'dataDirectory' field in User Config ('{data_directory_path_in_config}'). "
                    f"Using provided folder_path: '{self._folder_path}'.",
                    UserWarning,
                    stacklevel=2,
                )

            directory_structure = self._user_config.get("directoryStructure", [])
            config_fields = self._user_config.keys()
            fixed_path_entries = [key for key in directory_structure if key in config_fields]
            fixed_folders = [self._user_config[key] for key in fixed_path_entries]
            fixed_data_path = self._folder_path / "/".join(fixed_folders)

            if not fixed_data_path.exists():
                raise FileNotFoundError(
                    f"Expected directory structure not found: '{fixed_data_path}'\n"
                    f"Base folder: '{self._folder_path}'\n"
                    f"Directory structure from config: {directory_structure}\n"
                    f"Fixed path components: {fixed_folders}\n"
                    f"Please verify that:\n"
                    f"  1. The 'directoryStructure' in your User Config matches your actual folder structure\n"
                    f"  2. The fixed fields ({', '.join(fixed_path_entries)}) are correctly set\n"
                    f"  3. The folder '{fixed_data_path.name}' exists under '{fixed_data_path.parent}'"
                )

            miniscope_devices = self._user_config.get("devices", {}).get("miniscopes", {})
            if not miniscope_devices:
                raise ValueError("'devices[miniscopes]' is missing from the provided User Config file.")
            self._device_names = list(miniscope_devices.keys())
            # Create CamelCase mapping for device names
            self._device_names_camel_case = {name: to_camel_case(name) for name in self._device_names}

            all_paths = [p for p in fixed_data_path.glob("**") if p.is_dir()]
            device_folders_dict = {}
            for device_name in self._device_names:
                device_folders_dict[device_name] = [p for p in all_paths if p.name == device_name]

            self._interface_to_device_mapping = {}
            for device_name in self._device_names:
                # Iterate over all the folders found for this device
                # And create a MiniscopeImagingInterface for each
                for device_folder_path in device_folders_dict[device_name]:
                    # Use as_posix() to ensure forward slashes on all platforms and avoid windows backslashes
                    interface_name = device_folder_path.relative_to(fixed_data_path).as_posix()
                    interface = MiniscopeImagingInterface(folder_path=device_folder_path)
                    data_interfaces[interface_name] = interface
                    self._interface_to_device_mapping[interface_name] = device_name

                    # Check for head orientation data in the same device folder
                    head_orientation_file_path = device_folder_path / "headOrientation.csv"
                    if head_orientation_file_path.exists():
                        head_orientation_interface_name = f"{interface_name}/HeadOrientation"
                        # Use device name in CamelCase for unique metadata key
                        device_name_camel = self._device_names_camel_case[device_name]
                        # Include relative path to distinguish different sessions
                        interface_relative_path = interface_name.replace("/", "")
                        if interface_relative_path.endswith(device_name):
                            interface_relative_path = interface_relative_path[: -len(device_name)]
                        metadata_key = f"TimeSeriesMiniscopeHeadOrientation{device_name_camel}{interface_relative_path}"
                        data_interfaces[head_orientation_interface_name] = MiniscopeHeadOrientationInterface(
                            file_path=head_orientation_file_path,
                            metadata_key=metadata_key,
                        )
                        self._interface_to_device_mapping[head_orientation_interface_name] = device_name
        else:
            # Legacy mode: use _MiniscopeMultiRecordingInterface for backwards compatibility
            default_interface = _MiniscopeMultiRecordingInterface(folder_path=folder_path)
            default_metadata = default_interface.get_metadata()
            device_metadata = default_metadata["Ophys"]["Device"][0]
            device_name = device_metadata.get("name", "Miniscope")
            sanitized_device_name = device_name.replace(" ", "_")
            default_interface._miniscope_device_label = sanitized_device_name
            default_interface._device_name_from_metadata = device_name
            default_interface._device_metadata_index = 0
            default_interface._imaging_plane_metadata_index = 0
            interface_name = f"Miniscope"
            data_interfaces[interface_name] = default_interface
            self._interface_to_device_mapping = {interface_name: device_name}
            self._device_names = [device_name]
            # Create CamelCase mapping for device names
            self._device_names_camel_case = {device_name: to_camel_case(device_name)}

        super().__init__(data_interfaces=data_interfaces)

        # Attempt to initialize the behavior interface; skip gracefully if the expected files are absent.
        try:
            self.data_interface_objects["MiniscopeBehavCam"] = MiniscopeBehaviorInterface(folder_path=folder_path)
        except AssertionError:
            if self.verbose:
                print(
                    "Miniscope behavior videos were not found under the provided folder and will be omitted from conversion."
                )

        # Align session start times across all imaging interfaces
        self._align_session_start_times()

    def _is_head_orientation_interface(self, interface_name: str) -> bool:
        """Check if an interface name corresponds to a head orientation interface."""
        return interface_name.endswith("/HeadOrientation")

    def _get_ophys_interface_names(self) -> list[str]:
        """Get names of ophys interfaces, excluding behavior and head orientation interfaces."""
        return [
            k
            for k in self.data_interface_objects
            if k != "MiniscopeBehavCam" and not self._is_head_orientation_interface(k)
        ]

    def _get_head_orientation_interface_names(self) -> list[str]:
        """Get names of head orientation interfaces."""
        return [k for k in self.data_interface_objects if self._is_head_orientation_interface(k)]

    def _align_session_start_times(self):
        """
        Align all Miniscope imaging interfaces to a common session start time.

        For each interface:
        1. Extract its session_start_time from the session-level metaData.json
        2. Find the minimum session_start_time across all interfaces
        3. Shift each interface's timestamps by (session_start_time - min_session_start_time)

        This ensures that sessions recorded at different times maintain their temporal relationship.
        """
        from neuroconv.datainterfaces.ophys.miniscope.miniscopeimagingdatainterface import (
            _MiniscopeMultiRecordingInterface,
        )

        ophys_interface_names = self._get_ophys_interface_names()

        session_start_times = {}
        for interface_name in ophys_interface_names:
            interface = self.data_interface_objects[interface_name]

            # MiniscopeImagingInterface (config file mode) has _device_folder_path
            # _MiniscopeMultiRecordingInterface (legacy mode) has _recording_start_times
            if isinstance(interface, _MiniscopeMultiRecordingInterface):
                session_start_time = interface._recording_start_times[0]
            else:
                device_folder_path = interface._device_folder_path
                session_start_time = interface._get_session_start_time(folder_path=device_folder_path.parent)
            session_start_times[interface_name] = session_start_time

        # Find the minimum session_start_time (this becomes the reference)
        min_session_start_time = min(session_start_times.values())
        self._converter_session_start_time = min_session_start_time

        # Align each ophys interface's timestamps
        for interface_name, session_start_time in session_start_times.items():
            interface = self.data_interface_objects[interface_name]
            time_offset = (session_start_time - min_session_start_time).total_seconds()
            interface.set_aligned_starting_time(aligned_starting_time=time_offset)

        # Align head orientation interfaces with their paired imaging interfaces
        for ho_interface_name in self._get_head_orientation_interface_names():
            # Extract the paired imaging interface name (remove "/HeadOrientation" suffix)
            paired_interface_name = ho_interface_name.rsplit("/HeadOrientation", 1)[0]
            if paired_interface_name in session_start_times:
                ho_interface = self.data_interface_objects[ho_interface_name]
                session_start_time = session_start_times[paired_interface_name]
                time_offset = (session_start_time - min_session_start_time).total_seconds()
                aligned_timestamps = ho_interface.get_timestamps() + time_offset
                ho_interface.set_aligned_timestamps(aligned_timestamps)

    def get_metadata(self):
        from neuroconv.tools.roiextractors.roiextractors import (
            _get_default_ophys_metadata,
        )

        default_ophys_metadata = _get_default_ophys_metadata()
        metadata = super().get_metadata()

        # Use the minimum session start time if it was calculated during alignment
        metadata["NWBFile"]["session_start_time"] = self._converter_session_start_time

        # Update Device metadata to use CamelCase names
        if "Ophys" in metadata and "Device" in metadata["Ophys"]:
            for device_metadata in metadata["Ophys"]["Device"]:
                original_name = device_metadata["name"]
                if original_name in self._device_names_camel_case:
                    device_metadata["name"] = self._device_names_camel_case[original_name]

        ophys_interface_names = self._get_ophys_interface_names()

        imaging_plane_metadata = []
        # Required by the schema
        default_optical_channel = default_ophys_metadata["Ophys"]["ImagingPlane"][0]["optical_channel"]
        for device_name in self._device_names:
            device_name_camel = self._device_names_camel_case[device_name]
            metadata_entry = {
                "name": f"ImagingPlane{device_name_camel}",
                "description": f"Imaging plane for {device_name} Miniscope device.",
                "optical_channel": default_optical_channel,
                "device": device_name_camel,
            }
            imaging_plane_metadata.append(metadata_entry)

        series_metadata = []
        for interface_name in ophys_interface_names:
            device_name = self._interface_to_device_mapping[interface_name]
            device_name_camel = self._device_names_camel_case[device_name]
            # Remove slashes and strip device folder name from the end of interface path
            # E.g., "2025_06_12/15_15_04/ACC_miniscope2" -> "2025_06_1215_15_04"
            interface_relative_path = interface_name.replace("/", "")
            # Remove the device name from the end if present
            if interface_relative_path.endswith(device_name):
                interface_relative_path = interface_relative_path[: -len(device_name)]
            imaging_plane_name = f"ImagingPlane{device_name_camel}"
            metadata_entry = {
                "name": f"OnePhotonSeries{device_name_camel}{interface_relative_path}",
                "imaging_plane": imaging_plane_name,
            }
            series_metadata.append(metadata_entry)

        metadata["Ophys"]["OnePhotonSeries"] = series_metadata
        metadata["Ophys"]["ImagingPlane"] = imaging_plane_metadata

        return metadata

    def get_conversion_options_schema(self) -> dict:
        """Allow standard stub options alongside per-interface schemas."""

        schema = super().get_conversion_options_schema()

        # Add top-level stub options for converter-wide settings
        schema["properties"]["stub_test"] = {
            "type": "boolean",
            "default": False,
            "description": "If True, limit each Miniscope segment to 'stub_samples' samples during conversion.",
        }
        schema["properties"]["stub_samples"] = {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "Number of samples (frames) to include when 'stub_test' is enabled.",
        }
        schema["properties"]["stub_frames"] = {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "Deprecated. Use 'stub_samples' instead. Number of frames to include when 'stub_test' is enabled.",
        }

        # Note: Individual interfaces inherit stub_samples from BaseImagingExtractorInterface
        # which automatically infers it from the add_to_nwbfile method signature

        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
    ):
        """Add Miniscope interfaces to the provided NWBFile."""
        import warnings

        # Handle deprecation of stub_frames
        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_samples = stub_frames

        conversion_options = conversion_options.copy() if conversion_options else {}
        stub_test = conversion_options.pop("stub_test", stub_test)
        stub_samples = conversion_options.pop("stub_samples", conversion_options.pop("stub_frames", stub_samples))

        if metadata is None:
            metadata = self.get_metadata()

        ophys_interface_names = self._get_ophys_interface_names()
        conversion_options_base = {interface_name: {} for interface_name in ophys_interface_names}
        for series_index, interface_name in enumerate(ophys_interface_names):
            conversion_options_base[interface_name]["photon_series_index"] = series_index
            conversion_options_base[interface_name]["stub_test"] = stub_test
            conversion_options_base[interface_name]["stub_samples"] = stub_samples

        conversion_options_base.update(conversion_options)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            conversion_options=conversion_options_base,
        )

    def run_conversion(
        self,
        nwbfile_path: str | None = None,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
        **kwargs,
    ) -> None:
        """
        Run the NWB conversion process for the instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path : str, optional
            Path where the NWBFile will be written. If None, the file is handled in-memory.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to be written to the file. If None, a new NWBFile is created.
        metadata : dict, optional
            Metadata dictionary with information to create the NWBFile. If None, metadata is auto-generated.
        overwrite : bool, optional
            If True, overwrites the existing NWBFile at `nwbfile_path`. If False (default), data is appended.
        stub_test : bool, optional
            If True, only a subset of the data (up to `stub_samples`) is written for testing purposes,
            by default False.
        stub_frames : int, optional
            Deprecated. Use `stub_samples` instead.
        stub_samples : int, optional
            The number of samples (frames) to include in the subset if `stub_test` is True, by default 100.
        **kwargs
            Additional keyword arguments passed to the parent NWBConverter.run_conversion method.
        """
        import warnings

        # Handle deprecation of stub_frames
        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_samples = stub_frames

        # Get existing conversion_options or create empty dict
        conversion_options = kwargs.pop("conversion_options", {})

        # Apply stub_test and stub_frames to all imaging interfaces
        # Note: Using stub_frames for schema compatibility; the interface converts to stub_samples internally
        ophys_interface_names = self._get_ophys_interface_names()
        conversion_options_base = {interface_name: {} for interface_name in ophys_interface_names}
        for series_index, interface_name in enumerate(ophys_interface_names):
            conversion_options_base[interface_name]["photon_series_index"] = series_index
            conversion_options_base[interface_name]["stub_test"] = stub_test
            conversion_options_base[interface_name]["stub_samples"] = stub_samples

        conversion_options_base.update(conversion_options)

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            conversion_options=conversion_options_base,
            **kwargs,
        )
